#!/usr/bin/env python3
"""Causal reconstruction of the supplied solar-flare manuscript.

Uses raw linear XRS-B flux, right-aligned db2/cD3 energy, trailing
percentiles, causal persistence/eventization, and independent NOAA peaks.
Original unpublished implementation and April label selection are unavailable.
"""
from __future__ import annotations
import argparse
from collections import deque
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import platform
import sys
import zipfile
import numpy as np
import pandas as pd
import pywt


@dataclass(frozen=True)
class Config:
    wavelet: str = 'db2'
    level: int = 3
    extension_mode: str = 'symmetric'
    window_minutes: int = 30
    decision_minutes: int = 2
    horizon_minutes: int = 360
    warmup_minutes: int = 120
    prediction_quantile: float = 0.80
    detection_quantile: float = 0.95
    quantile_method: str = 'linear'
    persistence_minutes: int = 4
    merge_gap_minutes: int = 12
    interpolate_max_missing_minutes: int = 2
    prediction_min_lead_minutes: int = 10
    prediction_max_lead_minutes: int = 90
    detection_tolerance_minutes: int = 10


ALERT_COLUMNS = ['alert_id','stream','start_time','crossing_start_time','end_time',
                 'priority','energy_at_start','threshold_at_start','flux_at_start',
                 'raw_alerts_merged','segment_id','right_censored']
MATCH_COLUMNS = ['alert_id','stream','alert_start_time','crossing_start_time','event_id',
                 'noaa_peak_time','noaa_class','lead_minutes','offset_minutes',
                 'priority','timing_basis']


def read_goes(path: Path, months: list[str]):
    pieces=[]
    usecols=['time','quad_diode','xrsb_flux','xrsb_flag']
    def consume(f):
        for chunk in pd.read_csv(f,usecols=usecols,chunksize=250000):
            keep=chunk.time.astype(str).str.slice(0,7).isin(months)
            pieces.append(chunk.loc[keep])
    if path.suffix.lower()=='.zip':
        with zipfile.ZipFile(path) as z:
            names=[n for n in z.namelist() if n.lower().endswith('.csv')]
            if len(names)!=1: raise ValueError('The GOES ZIP must contain exactly one CSV')
            with z.open(names[0]) as f: consume(f)
    else: consume(path)
    frame=pd.concat(pieces,ignore_index=True)
    frame['time']=pd.to_datetime(frame.time,utc=True)
    g=frame.groupby('time')
    if not g.xrsb_flux.nunique(dropna=False).le(1).all():
        raise ValueError('Duplicate timestamps have conflicting XRS-B flux values')
    if not g.xrsb_flag.nunique(dropna=False).le(1).all():
        raise ValueError('Duplicate timestamps have conflicting quality flags')
    raw_count=len(frame)
    frame=frame.sort_values(['time','quad_diode']).drop_duplicates('time').set_index('time')
    return frame,raw_count


def regularize(frame: pd.DataFrame, month: str, full_month=True):
    start=pd.Timestamp(month+'-01',tz='UTC')
    end=start+pd.offsets.MonthBegin(1)
    part=frame.loc[(frame.index>=start)&(frame.index<end)].copy()
    if not full_month:
        end=part.index.max()+pd.Timedelta(minutes=1)
    grid=pd.date_range(start,end,freq='min',inclusive='left')
    return part.reindex(grid),start,end


def causal_gap_fill(raw: np.ndarray, cfg: Config):
    """Return backfilled flux with explicit information-availability times.

    A missing minute is never used for an alert at its own timestamp.
    Interpolated past samples may enter subsequent windows only after the
    right endpoint has arrived. Long/unbounded gaps remain missing.
    """
    raw=np.asarray(raw,dtype=float)
    observed=np.isfinite(raw)&(raw>=0)
    used=np.where(observed,raw,np.nan)
    availability=np.arange(len(raw),dtype=np.int64)
    availability[~observed]=len(raw)+1
    interpolated=np.zeros(len(raw),dtype=bool)
    prev=-1
    for i in np.flatnonzero(observed):
        missing=i-prev-1
        if prev>=0 and 0<missing<=cfg.interpolate_max_missing_minutes:
            used[prev+1:i]=np.linspace(raw[prev],raw[i],missing+2)[1:-1]
            availability[prev+1:i]=i
            interpolated[prev+1:i]=True
        prev=i
    return used,observed,availability,interpolated


def compute_decisions(part: pd.DataFrame, cfg=Config()):
    raw=part.xrsb_flux.to_numpy(dtype=float)
    used,observed,availability,interpolated=causal_gap_fill(raw,cfg)
    n=len(part)
    ticks=np.arange(0,n,cfg.decision_minutes)
    energy=np.full(len(ticks),np.nan)
    for j,t in enumerate(ticks):
        left=t-cfg.window_minutes+1
        if left<0 or not observed[t]: continue
        window=used[left:t+1]
        if not np.isfinite(window).all() or np.max(availability[left:t+1])>t: continue
        details=pywt.wavedec(window,cfg.wavelet,mode=cfg.extension_mode,level=cfg.level)[1]
        energy[j]=float(np.dot(details,details))
    pred=np.full(len(ticks),np.nan)
    det=pred.copy();rank=pred.copy();history_count=np.zeros(len(ticks),dtype=int)
    history=deque()
    for j,t in enumerate(ticks):
        while history and history[0][0]<t-cfg.horizon_minutes: history.popleft()
        if np.isfinite(energy[j]): history.append((t,energy[j]))
        if history:
            values=np.array([v for _,v in history])
            pred[j],det[j]=np.quantile(values,[cfg.prediction_quantile,cfg.detection_quantile],method=cfg.quantile_method)
            history_count[j]=len(values)
            if np.isfinite(energy[j]):rank[j]=np.mean(values<=energy[j])
    decisions=pd.DataFrame({
        'time':part.index[ticks], 'minute_index':ticks, 'flux':raw[ticks],
        'energy':energy,'prediction_threshold':pred,'detection_threshold':det,
        'priority_rank':rank,'threshold_history_count':history_count,
        'observed_right_edge':observed[ticks], 'feature_valid':np.isfinite(energy),
        'after_warmup':ticks>=cfg.warmup_minutes,
    })
    decisions['decision_eligible']=decisions.feature_valid&decisions.after_warmup
    decisions['prediction_above']=decisions.decision_eligible&(energy>pred)
    decisions['detection_above']=decisions.decision_eligible&(energy>det)
    minutes=part.copy()
    minutes['raw_flux']=raw;minutes['flux_used']=used;minutes['observed']=observed
    minutes['interpolated']=interpolated
    minutes['available_at']=pd.to_datetime([part.index[v] if v<n else pd.NaT for v in availability],utc=True)
    return decisions,minutes


def eventize(decisions: pd.DataFrame, stream: str, cfg=Config(), month_end=None):
    """Online confirmation with stable event starts and short-gap ID reuse."""
    events=[];active=None;pending=None;pending_cross=None;segment=0
    threshold=stream+'_threshold';above_col=stream+'_above'
    for r in decisions.to_dict('records'):
        t=r['time']
        if not r['decision_eligible']:
            if active is not None:
                active['end_time']=t;active['right_censored']=False
            active=None;pending=None;pending_cross=None;segment+=1
            continue
        if not r[above_col]:
            if active is not None:
                active['end_time']=t;active['right_censored']=False
            active=None;pending=None;pending_cross=None
            continue
        if active is not None:
            active['end_time']=min(t+pd.Timedelta(minutes=cfg.decision_minutes),month_end) if month_end is not None else t+pd.Timedelta(minutes=cfg.decision_minutes)
            active['right_censored']=True
            continue
        if pending is None:pending=t;pending_cross=r
        elapsed=(t-pending).total_seconds()/60
        if elapsed<cfg.persistence_minutes:continue
        if events and events[-1]['segment_id']==segment and (t-events[-1]['end_time']).total_seconds()/60<=cfg.merge_gap_minutes:
            active=events[-1];active['raw_alerts_merged']+=1
        else:
            active={
                'alert_id':f"{stream[0].upper()}-{t.strftime('%Y%m')}-{len(events)+1:04d}",
                'stream':stream,'start_time':t,'crossing_start_time':pending,
                'end_time':t,'priority':float(r['priority_rank']),
                'energy_at_start':float(r['energy']),'threshold_at_start':float(r[threshold]),
                'flux_at_start':float(r['flux']),'raw_alerts_merged':1,
                'segment_id':segment,'right_censored':True,
            }
            events.append(active)
        active['end_time']=min(t+pd.Timedelta(minutes=cfg.decision_minutes),month_end) if month_end is not None else t+pd.Timedelta(minutes=cfg.decision_minutes)
        active['right_censored']=True
        pending=None;pending_cross=None
    return pd.DataFrame(events,columns=ALERT_COLUMNS)


def match_alerts(alerts: pd.DataFrame, refs: pd.DataFrame, stream: str,
                 cfg=Config(), timing_basis='confirmed'):
    column='start_time' if timing_basis=='confirmed' else 'crossing_start_time'
    ordered=alerts.sort_values([column,'alert_id'])
    refs=refs.sort_values(['peak_time','event_id']).reset_index(drop=True)
    available=set(range(len(refs)));matches=[]
    for alert in ordered.to_dict('records'):
        t=alert[column]
        choices=[]
        for idx in available:
            ref=refs.iloc[idx]
            lead=(ref.peak_time-t).total_seconds()/60
            if stream=='prediction':
                if cfg.prediction_min_lead_minutes<=lead<=cfg.prediction_max_lead_minutes:
                    choices.append((lead,ref.peak_time,str(ref.event_id),idx))
            elif abs(lead)<=cfg.detection_tolerance_minutes:
                choices.append((abs(lead),ref.peak_time,str(ref.event_id),idx))
        if not choices:continue
        _,_,_,idx=min(choices)
        available.remove(idx);ref=refs.iloc[idx]
        lead=(ref.peak_time-t).total_seconds()/60
        matches.append({
            'alert_id':alert['alert_id'],'stream':stream,'alert_start_time':t,
            'crossing_start_time':alert['crossing_start_time'],'event_id':ref.event_id,
            'noaa_peak_time':ref.peak_time,'noaa_class':ref['class'],
            'lead_minutes':lead,'offset_minutes':-lead,
            'priority':alert['priority'],'timing_basis':timing_basis,
        })
    matched=pd.DataFrame(matches,columns=MATCH_COLUMNS)
    tp=len(matched);fp=len(alerts)-tp;fn=len(refs)-tp
    precision=tp/len(alerts) if len(alerts) else 0.0
    recall=tp/len(refs) if len(refs) else np.nan
    f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else np.nan
    metrics={'stream':stream,'timing_basis':timing_basis,'alerts_issued':len(alerts),
             'noaa_cmx_events':len(refs),'TP':tp,'FP':fp,'FN':fn,
             'precision':precision,'recall':recall,'F1':f1,
             'lead_n':tp if stream=='prediction' else 0,
             'lead_min_minutes':np.nan,'lead_Q1_minutes':np.nan,'lead_median_minutes':np.nan,
             'lead_Q3_minutes':np.nan,'lead_max_minutes':np.nan,
             'median_absolute_detection_offset_minutes':np.nan}
    if tp and stream=='prediction':
        qs=np.quantile(matched.lead_minutes,[0,.25,.5,.75,1],method='linear')
        for key,value in zip(['lead_min_minutes','lead_Q1_minutes','lead_median_minutes','lead_Q3_minutes','lead_max_minutes'],qs):metrics[key]=float(value)
    if tp and stream=='detection':metrics['median_absolute_detection_offset_minutes']=float(np.median(np.abs(matched.offset_minutes)))
    if tp:
        assert matched.alert_id.is_unique and matched.event_id.is_unique
    unmatched_alerts=alerts.loc[~alerts.alert_id.isin(matched.alert_id)].copy()
    unmatched_refs=refs.loc[~refs.event_id.isin(matched.event_id)].copy()
    return matched,unmatched_alerts,unmatched_refs,metrics


def write_csv(frame: pd.DataFrame,path: Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    frame.to_csv(temporary,index=False,date_format='%Y-%m-%dT%H:%M:%SZ')
    temporary.replace(path)


def gaps_for_month(minutes: pd.DataFrame):
    unavailable=~minutes.observed.to_numpy()
    records=[];i=0
    while i<len(minutes):
        if not unavailable[i]:i+=1;continue
        j=i
        while j<len(minutes) and unavailable[j]:j+=1
        records.append({'start_time':minutes.index[i],'end_time':minutes.index[j-1]+pd.Timedelta(minutes=1),
                        'missing_minutes':j-i,'interpolated':bool(minutes.interpolated.iloc[i:j].all())})
        i=j
    return pd.DataFrame(records,columns=['start_time','end_time','missing_minutes','interpolated'])


def evaluate_month(part,month,labels,cfg,out):
    start=pd.Timestamp(month+'-01',tz='UTC');end=start+pd.offsets.MonthBegin(1)
    out.mkdir(parents=True,exist_ok=True)
    decisions,minutes=compute_decisions(part,cfg)
    all_refs=labels.loc[(labels.peak_time>=start)&(labels.peak_time<end)&labels['class'].str[0].isin(['C','M','X'])].copy()
    refs=all_refs.loc[all_refs.peak_time>=start+pd.Timedelta(minutes=cfg.warmup_minutes)].copy()
    refs['goes_flux_at_peak']=part.xrsb_flux.reindex(pd.DatetimeIndex(refs.peak_time)).to_numpy()
    refs['peak_flux_available']=np.isfinite(refs.goes_flux_at_peak)
    write_csv(refs,out/'noaa_reference_events.csv')
    write_csv(decisions,out/'decision_features_and_thresholds.csv')
    write_csv(minutes.rename_axis('time').reset_index(),out/'goes_processed_minutes.csv')
    gaps=gaps_for_month(minutes);write_csv(gaps,out/'data_gaps.csv')
    rows=[];sens=[];daily=[]
    for stream in ['prediction','detection']:
        alerts=eventize(decisions,stream,cfg,end)
        matches,fp,fn,metric=match_alerts(alerts,refs,stream,cfg)
        metric.update(month=month,run='confirmed_4min',persistence_minutes=cfg.persistence_minutes)
        rows.append(metric)
        write_csv(alerts,out/f'{stream}_alerts.csv')
        write_csv(matches,out/f'{stream}_matches.csv')
        write_csv(fp,out/f'{stream}_false_positives.csv')
        write_csv(fn,out/f'{stream}_false_negatives.csv')
        # Display priorities never enter thresholding or matching.
        for basis,persistence,case in [('crossing',cfg.persistence_minutes,'initial_crossing_retrospective'),('confirmed',2,'two_positive_decisions')]:
            alt_alerts=alerts if persistence==cfg.persistence_minutes else eventize(decisions,stream,replace(cfg,persistence_minutes=persistence),end)
            alt_matches,_,_,m=match_alerts(alt_alerts,refs,stream,cfg,basis)
            m.update(month=month,run=case,persistence_minutes=persistence)
            sens.append(m)
            write_csv(alt_matches,out/'sensitivity'/f'{case}_{stream}_matches.csv')
            if persistence!=cfg.persistence_minutes:write_csv(alt_alerts,out/'sensitivity'/f'{case}_{stream}_alerts.csv')
        for day in pd.date_range(start,end,freq='D',inclusive='left'):
            stop=day+pd.Timedelta(days=1)
            na=int(((refs.peak_time>=day)&(refs.peak_time<stop)).sum())
            a=int(((alerts.start_time>=day)&(alerts.start_time<stop)).sum()) if len(alerts) else 0
            tp_alert=int(((matches.alert_start_time>=day)&(matches.alert_start_time<stop)).sum()) if len(matches) else 0
            tp_peak=int(((matches.noaa_peak_time>=day)&(matches.noaa_peak_time<stop)).sum()) if len(matches) else 0
            daily.append({'date':day.strftime('%Y-%m-%d'),'stream':stream,'alerts_issued':a,
                          'matched_alerts_by_alert_date':tp_alert,'false_positives_by_alert_date':a-tp_alert,
                          'noaa_peaks':na,'matched_peaks_by_peak_date':tp_peak,'false_negatives_by_peak_date':na-tp_peak})
    write_csv(pd.DataFrame(rows),out/'metrics.csv')
    write_csv(pd.DataFrame(sens),out/'sensitivity_metrics.csv')
    write_csv(pd.DataFrame(daily),out/'daily_counts.csv')
    audit={'month':month,'minute_grid_size':len(part),'raw_missing_flux_minutes':int((~minutes.observed).sum()),
           'interpolated_missing_minutes':int(minutes.interpolated.sum()),
           'long_or_unbounded_missing_minutes':int(((~minutes.observed)&(~minutes.interpolated)).sum()),
           'finite_flux_nonzero_quality_flag_minutes':int((minutes.observed&minutes.xrsb_flag.fillna(0).ne(0)).sum()),
           'total_decision_ticks':len(decisions),'valid_feature_ticks':int(decisions.feature_valid.sum()),
           'eligible_decision_ticks_after_warmup':int(decisions.decision_eligible.sum()),
           'eligible_decision_coverage_after_warmup':float(decisions.decision_eligible.sum()/decisions.after_warmup.sum()),
           'noaa_full_month_cmx':len(all_refs),'warmup_excluded_noaa_cmx':len(all_refs)-len(refs),
           'evaluated_noaa_cmx':len(refs),'noaa_peaks_missing_GOES_flux':int((~refs.peak_flux_available).sum()),
           'reference_events_removed_for_data_gaps':0,
           'history_includes_current_feature':True,'quality_flag_filter_applied':False}
    (out/'data_audit.json').write_text(json.dumps(audit,indent=2))
    print(month, json.dumps([{k:r[k] for k in ['stream','alerts_issued','noaa_cmx_events','TP','FP','FN','precision','recall','F1','lead_median_minutes']} for r in rows]),flush=True)
    return rows,sens,audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--goes',type=Path,required=True)
    parser.add_argument('--noaa',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--months',nargs='+',default=['2022-04','2022-05','2022-06','2022-07'])
    args=parser.parse_args();cfg=Config()
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'configuration.json').write_text(json.dumps(asdict(cfg),indent=2))
    labels=pd.read_csv(args.noaa,keep_default_na=False)
    for field in ['start_time','peak_time','end_time']:labels[field]=pd.to_datetime(labels[field],utc=True)
    if not labels.event_id.is_unique:raise ValueError('NOAA peak identifiers must be unique')
    goes,raw_count=read_goes(args.goes,args.months)
    metrics=[];sens=[];audits=[]
    for month in args.months:
        part,_,_=regularize(goes,month)
        m,s,a=evaluate_month(part,month,labels,cfg,args.out/'months'/month)
        metrics.extend(m);sens.extend(s);audits.append(a)
    write_csv(pd.DataFrame(metrics),args.out/'monthly_metrics.csv')
    write_csv(pd.DataFrame(sens),args.out/'sensitivity_metrics.csv')
    write_csv(pd.DataFrame(audits),args.out/'data_coverage.csv')
    primary=pd.DataFrame(metrics).loc[lambda d:d.month.isin(['2022-05','2022-06','2022-07'])]
    pooled=[]
    for stream,g in primary.groupby('stream',sort=False):
        tp=int(g.TP.sum());fp=int(g.FP.sum());fn=int(g.FN.sum())
        pooled.append({'months':'2022-05 to 2022-07','stream':stream,'alerts_issued':int(g.alerts_issued.sum()),
                       'noaa_cmx_events':int(g.noaa_cmx_events.sum()),'TP':tp,'FP':fp,'FN':fn,
                       'precision':tp/(tp+fp) if tp+fp else 0,'recall':tp/(tp+fn) if tp+fn else np.nan,
                       'F1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else np.nan})
    write_csv(pd.DataFrame(pooled),args.out/'pooled_May_June_July_metrics.csv')
    metadata={'GOES_source_file':args.goes.name,'GOES_source_sha256':hashlib.sha256(args.goes.read_bytes()).hexdigest(),
              'NOAA_catalog_file':args.noaa.name,'NOAA_catalog_sha256':hashlib.sha256(args.noaa.read_bytes()).hexdigest(),
              'raw_selected_GOES_rows':raw_count,'deduplicated_GOES_minutes':len(goes),
              'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'PyWavelets':pywt.__version__,
              'baseline_status':'Not reproduced: SMA window, adaptive rule and April search grid were not supplied',
              'replication_status':'Manuscript reconstruction with documented choices; original April results not reproduced'}
    (args.out/'run_metadata.json').write_text(json.dumps(metadata,indent=2))


if __name__=='__main__':main()
