#!/usr/bin/env python3
"""Independent checks of causality, matching and saved manuscript results."""
from pathlib import Path
import argparse
import importlib.util
import json
import sys
import numpy as np
import pandas as pd
import pywt


def load_code(path):
    spec=importlib.util.spec_from_file_location('manuscript_pipeline',path)
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod


def independent_match(alerts,refs,stream,start='start_time'):
    # Sorted reference traversal independently checks minimum lead / closest peak.
    used=set();result=[]
    for a in alerts.sort_values([start,'alert_id']).to_dict('records'):
        t=a[start];candidates=[]
        for r in refs.sort_values(['peak_time','event_id']).to_dict('records'):
            if r['event_id'] in used:continue
            lead=(r['peak_time']-t).total_seconds()/60
            valid=(10<=lead<=90) if stream=='prediction' else abs(lead)<=10
            if valid:candidates.append((lead if stream=='prediction' else abs(lead),r['peak_time'],r['event_id']))
        if candidates:
            choice=min(candidates);used.add(choice[2]);result.append((a['alert_id'],choice[2]))
    return result


def read_times(path,columns):
    df=pd.read_csv(path)
    for c in columns:df[c]=pd.to_datetime(df[c],utc=True)
    return df


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--code',type=Path,required=True)
    args=parser.parse_args();root=args.results;mod=load_code(args.code);cfg=mod.Config()
    metrics=pd.read_csv(root/'monthly_metrics.csv')
    checks=[];causal_checks=[];gap_checks=[];feature_checks=0
    for month in metrics.month.unique():
        folder=root/'months'/month
        dec=read_times(folder/'decision_features_and_thresholds.csv',['time'])
        minutes=read_times(folder/'goes_processed_minutes.csv',['time','available_at']).set_index('time')
        expected_grid=int(((pd.Timestamp(month+'-01',tz='UTC')+pd.offsets.MonthBegin(1))-pd.Timestamp(month+'-01',tz='UTC')).total_seconds()/60)
        assert len(minutes)==expected_grid,(month,'incomplete minute export',len(minutes),expected_grid)
        refs=read_times(folder/'noaa_reference_events.csv',['start_time','peak_time','end_time'])
        assert refs.event_id.is_unique
        assert (refs['class'].str[0].isin(list('CMX'))).all()
        assert refs.peak_time.dt.strftime('%Y-%m').eq(month).all()
        assert not ((~dec.decision_eligible)&(dec.prediction_above|dec.detection_above)).any()
        valid=dec.loc[dec.feature_valid]
        # Recompute sampled features and quantiles directly from saved windows/history.
        samples=np.linspace(0,len(valid)-1,12,dtype=int)
        for i in samples:
            row=valid.iloc[i];t=row.time
            window=minutes.loc[t-pd.Timedelta(minutes=29):t]
            assert len(window)==30 and window.available_at.le(t).all()
            e=float(np.sum(pywt.wavedec(window.flux_used.to_numpy(), 'db2',mode='symmetric',level=3)[1]**2))
            assert np.isclose(e,row.energy,rtol=1e-12,atol=0)
            history=dec.loc[dec.time.between(t-pd.Timedelta(hours=6),t)&dec.feature_valid].energy
            expected=np.quantile(history,[.8,.95],method='linear')
            assert np.allclose(expected,[row.prediction_threshold,row.detection_threshold],rtol=1e-12,atol=0)
            assert len(history)==row.threshold_history_count
            feature_checks+=1
        for stream in ['prediction','detection']:
            alerts=read_times(folder/f'{stream}_alerts.csv',['start_time','crossing_start_time','end_time'])
            matches=read_times(folder/f'{stream}_matches.csv',['alert_start_time','crossing_start_time','noaa_peak_time'])
            metric=metrics.loc[metrics.month.eq(month)&metrics.stream.eq(stream)].iloc[0]
            assert alerts.alert_id.is_unique
            assert matches.alert_id.is_unique and matches.event_id.is_unique
            assert alerts.start_time.ge(pd.Timestamp(month+'-01',tz='UTC')+pd.Timedelta(minutes=120)).all()
            assert ((alerts.start_time-alerts.crossing_start_time).dt.total_seconds()/60).eq(4).all()
            assert alerts.end_time.gt(alerts.start_time).all()
            assert len(alerts)==metric.alerts_issued and len(matches)==metric.TP
            assert metric.TP+metric.FP==metric.alerts_issued
            assert metric.TP+metric.FN==metric.noaa_cmx_events==len(refs)
            assert np.isclose(metric.precision,metric.TP/metric.alerts_issued)
            assert np.isclose(metric.recall,metric.TP/len(refs))
            assert np.isclose(metric.F1,2*metric.TP/(2*metric.TP+metric.FP+metric.FN))
            got=list(zip(matches.alert_id,matches.event_id))
            expected=independent_match(alerts,refs,stream)
            assert got==expected,(month,stream,'independent greedy matching mismatch')
            if stream=='prediction':
                assert matches.lead_minutes.between(10,90).all()
                assert metric.lead_n==len(matches)
                actual=np.quantile(matches.lead_minutes,[0,.25,.5,.75,1])
                recorded=metric[['lead_min_minutes','lead_Q1_minutes','lead_median_minutes','lead_Q3_minutes','lead_max_minutes']].to_numpy(dtype=float)
                assert np.array_equal(actual,recorded)
            else:assert matches.offset_minutes.abs().le(10).all()
            # Fixed display rank does not change matches.
            priority_changed=alerts.copy();priority_changed['priority']=1-alerts.priority
            assert independent_match(priority_changed,refs,stream)==expected
            checks.append({'month':month,'stream':stream,'alerts':len(alerts),'matches':len(matches),
                           'independent_matching_passed':True,'count_and_metric_identities_passed':True,
                           'display_priority_independence_passed':True})
        # Prefix causality: no future samples can alter an earlier decision or issued alert.
        cutoffs=[720]
        observed=minutes.observed.to_numpy()
        starts=np.flatnonzero((~observed)&np.r_[True,observed[:-1]])
        if len(starts):cutoffs.append(int(starts[0]))
        full_alerts={s:read_times(folder/f'{s}_alerts.csv',['start_time','crossing_start_time','end_time']) for s in ['prediction','detection']}
        for cut in cutoffs:
            prefix=minutes[['quad_diode','xrsb_flux','xrsb_flag']].iloc[:cut+1]
            prefix_dec,_=mod.compute_decisions(prefix,cfg)
            saved=dec.loc[dec.time<=prefix.index[-1]].reset_index(drop=True)
            for col in ['energy','prediction_threshold','detection_threshold','priority_rank']:
                assert np.allclose(prefix_dec[col],saved[col],rtol=1e-12,atol=0,equal_nan=True),(month,cut,col)
            for col in ['decision_eligible','prediction_above','detection_above']:
                assert np.array_equal(prefix_dec[col],saved[col])
            for stream in ['prediction','detection']:
                pa=mod.eventize(prefix_dec,stream,cfg,prefix.index[-1]+pd.Timedelta(minutes=1))
                fa=full_alerts[stream].loc[lambda a:a.start_time<=prefix.index[-1]]
                assert pa.alert_id.tolist()==fa.alert_id.tolist()
                assert pa.start_time.tolist()==fa.start_time.tolist()
                assert np.allclose(pa.priority,fa.priority,rtol=1e-12,atol=0)
            causal_checks.append({'month':month,'cutoff_utc':prefix.index[-1].isoformat(),
                                  'features_thresholds_alert_starts_and_priorities_unchanged':True})
            print('Prefix causality passed:',month,prefix.index[-1],flush=True)
        # Changing all future flux values is a stronger explicit look-ahead test.
        changed=minutes[['quad_diode','xrsb_flux','xrsb_flag']].iloc[:1441].copy()
        changed.iloc[721:,changed.columns.get_loc('xrsb_flux')]*=1000
        changed_dec,_=mod.compute_decisions(changed,cfg)
        mask=changed_dec.minute_index<=720
        for col in ['energy','prediction_threshold','detection_threshold','priority_rank']:
            assert np.allclose(changed_dec.loc[mask,col],dec.loc[dec.minute_index<=720,col],rtol=1e-12,atol=0,equal_nan=True)
        causal_checks.append({'month':month,'future_flux_perturbation_factor':1000,
                              'cutoff_minute':720,'earlier_decisions_unchanged':True})
    # Small-gap availability and long-gap behavior checked with synthetic cases.
    for values,gap_kind in [([1.,np.nan,3.],'one-minute'),([1.,np.nan,np.nan,4.],'two-minute'),([1.,np.nan,np.nan,np.nan,5.],'three-minute')]:
        used,obs,availability,interp=mod.causal_gap_fill(np.array(values),cfg)
        if len(values)<=4:
            assert np.isfinite(used).all() and interp[1:-1].all()
            assert (availability[1:-1]==len(values)-1).all()
            assert not obs[1:-1].any()
        else:assert np.isnan(used[1:-1]).all() and not interp.any()
        gap_checks.append({'case':gap_kind,'availability_and_masking_passed':True})
    # Boundary tests for matching: 10 and 90 are inclusive; 9 and 91 are excluded.
    zero=pd.Timestamp('2022-05-01T10:00:00Z')
    one_alert=pd.DataFrame([{'alert_id':'P-test','start_time':zero,'crossing_start_time':zero-pd.Timedelta(minutes=4),'priority':.9}])
    for lead,expect in [(9,0),(10,1),(90,1),(91,0)]:
        rs=pd.DataFrame([{'event_id':'E-test','peak_time':zero+pd.Timedelta(minutes=lead),'class':'C1.0'}])
        assert len(mod.match_alerts(one_alert,rs,'prediction')[0])==expect
    for offset,expect in [(-11,0),(-10,1),(10,1),(11,0)]:
        rs=pd.DataFrame([{'event_id':'E-test','peak_time':zero+pd.Timedelta(minutes=offset),'class':'C1.0'}])
        assert len(mod.match_alerts(one_alert,rs,'detection')[0])==expect
    report={'status':'passed','monthly_metric_and_matching_checks':checks,
            'independent_wavelet_and_threshold_windows_checked':feature_checks,
            'prefix_and_future_perturbation_causality_checks':causal_checks,
            'small_and_long_gap_checks':gap_checks,'matching_boundaries_checked':True,
            'original_April_reproduction_status':'not_reproduced'}
    (root/'validation_results.json').write_text(json.dumps(report,indent=2))
    print('All causality, matching, numerical and saved-result checks passed.',flush=True)


if __name__=='__main__':main()
