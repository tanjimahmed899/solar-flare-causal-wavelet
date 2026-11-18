#!/usr/bin/env python3
"""Create figures and a report from completed causal-pipeline CSV results."""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from PIL import Image as PILImage
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.lib.pagesizes import A4

PRED='#21846C';DET='#B94040';FLUX='#203B5C';NOAA='#6B7280'
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,
                     'axes.grid':True,'grid.alpha':.15,'figure.facecolor':'white',
                     'savefig.facecolor':'white'})


def read_csv(path,times=()):
    d=pd.read_csv(path)
    for t in times:d[t]=pd.to_datetime(d[t],utc=True)
    return d


def save_figure(fig,path,*,dpi):
    """Validate a completed PNG before replacing the deliverable."""
    path=Path(path)
    temporary=path.with_name(path.name+'.tmp')
    try:
        fig.savefig(temporary,format='png',dpi=dpi)
        with PILImage.open(temporary) as rendered:
            rendered.verify()
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_month(root,month):
    f=root/'months'/month
    return {
        'minutes':read_csv(f/'goes_processed_minutes.csv',['time']).set_index('time'),
        'decisions':read_csv(f/'decision_features_and_thresholds.csv',['time']),
        'refs':read_csv(f/'noaa_reference_events.csv',['peak_time']),
        'prediction':read_csv(f/'prediction_alerts.csv',['start_time','end_time','crossing_start_time']),
        'detection':read_csv(f/'detection_alerts.csv',['start_time','end_time','crossing_start_time']),
        'prediction_matches':read_csv(f/'prediction_matches.csv',['alert_start_time','noaa_peak_time']),
        'detection_matches':read_csv(f/'detection_matches.csv',['alert_start_time','noaa_peak_time']),
    }


def timeline_figure(data,start,stop,path,title,monthly=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    m=data['minutes'].loc[(data['minutes'].index>=start)&(data['minutes'].index<stop)]
    d=data['decisions'].loc[lambda x:x.time.ge(start)&x.time.lt(stop)]
    refs=data['refs'].loc[lambda x:x.peak_time.ge(start)&x.peak_time.lt(stop)]
    fig,axes=plt.subplots(3,1,figsize=(12,6.3),sharex=True,gridspec_kw={'height_ratios':[2,1.45,.65]})
    ax,ae,aw=axes
    ax.plot(m.index,m.raw_flux,color=FLUX,lw=.85)
    ax.set_yscale('log');ax.set_ylabel('XRS-B flux (W/m²)')
    for y,label in [(1e-6,'C1'),(1e-5,'M1'),(1e-4,'X1')]:
        if m.raw_flux.max()>=y*.3:
            ax.axhline(y,color='#9CA3AF',lw=.6,ls=':')
            ax.text(.995,y,label,transform=ax.get_yaxis_transform(),ha='right',va='bottom',fontsize=8,color='#697587')
    ae.plot(d.time,d.energy,color=FLUX,lw=.75)
    ae.plot(d.time,d.prediction_threshold,color=PRED,lw=.8)
    ae.plot(d.time,d.detection_threshold,color=DET,lw=.8)
    ae.set_yscale('log');ae.set_ylabel('cD3 energy ((W/m²)²)')
    counts={}
    for stream,col,row in [('prediction',PRED,1),('detection',DET,0)]:
        alerts=data[stream]
        visible=alerts.loc[alerts.start_time.lt(stop)&alerts.end_time.gt(start)]
        for a in visible.to_dict('records'):
            left=max(a['start_time'],start);right=min(a['end_time'],stop)
            aw.broken_barh([(mdates.date2num(left),(right-left).total_seconds()/86400)],(row-.24,.48),facecolors=col,alpha=.75)
        issued=alerts.loc[alerts.start_time.ge(start)&alerts.start_time.lt(stop)]
        counts[stream]=len(issued)
        if len(issued):ax.scatter(issued.start_time,issued.flux_at_start,s=14 if monthly else 25,color=col,marker='o' if stream=='prediction' else 'x',zorder=4)
        matches=data[stream+'_matches'].loc[lambda x:x.alert_start_time.ge(start)&x.alert_start_time.lt(stop)]
        if len(matches) and stream=='prediction':
            matched_flux=alerts.set_index('alert_id').loc[matches.alert_id].flux_at_start.to_numpy()
            ax.scatter(matches.alert_start_time,matched_flux,color='#E8AA35',edgecolor='#7B580C',linewidth=.3,marker='*',s=38 if monthly else 85,zorder=5)
    for r in refs.to_dict('records'):
        peak=r['peak_time']
        ax.axvline(peak,color=NOAA,lw=.5,alpha=.3 if monthly else .45)
        aw.axvline(peak,color=NOAA,lw=.5,alpha=.45)
        if not monthly and r['class'][0] in 'MX':
            ax.text(peak,.95,r['class'],transform=ax.get_xaxis_transform(),rotation=90,ha='right',va='top',fontsize=8,color=DET)
    aw.set_yticks([0,1],['Detection','Prediction']);aw.set_ylim(-.6,1.6)
    aw.set_xlabel('Time (UTC)')
    if monthly:
        aw.xaxis.set_major_locator(mdates.DayLocator(interval=4))
        aw.xaxis.set_major_formatter(mdates.DateFormatter('%b %d',tz=start.tzinfo))
    else:
        aw.xaxis.set_major_locator(mdates.HourLocator(interval=4))
        aw.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M',tz=start.tzinfo))
    aw.set_xlim(start,stop)
    fig.suptitle(title,fontsize=13,color=FLUX,y=.98)
    fig.text(.08,.91,f'NOAA C/M/X peaks: {len(refs)}   Prediction starts: {counts["prediction"]}   Detection starts: {counts["detection"]}',fontsize=9,color='#536277')
    handles=[Line2D([],[],color=FLUX,label='GOES flux / energy'),Line2D([],[],color=PRED,label='Prediction / Q80'),
             Line2D([],[],color=DET,label='Detection / Q95'),Line2D([],[],color=NOAA,label='NOAA peak',ls=':'),
             Line2D([],[],marker='*',color='#E8AA35',linestyle='None',label='Matched Prediction',markersize=9)]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,-.001),ncol=5,frameon=False,fontsize=8)
    fig.subplots_adjust(top=.865,bottom=.14,left=.08,right=.98,hspace=.16)
    save_figure(fig,path,dpi=180);plt.close(fig)


def performance_figure(metrics,path):
    fig,axes=plt.subplots(1,2,figsize=(10.5,3.6),sharey=True)
    for ax,stream in zip(axes,['prediction','detection']):
        g=metrics.loc[metrics.stream.eq(stream)&metrics.month.ne('2022-04')]
        for col,c,mark in [('precision','#5E6FBB','o'),('recall','#DD9733','s'),('F1',PRED,'D')]:
            ax.plot(['May','June','July'],g[col],marker=mark,color=c,label=col.capitalize())
        ax.set_title(stream.capitalize());ax.set_ylim(0,1);ax.set_xlabel('2022 UTC month')
    axes[0].set_ylabel('Score');axes[1].legend(frameon=False,loc='upper right',fontsize=8)
    fig.suptitle('Monthly performance against NOAA C/M/X peaks',fontsize=12,color=FLUX)
    fig.tight_layout();save_figure(fig,path,dpi=200);plt.close(fig)


def lead_figure(cache,path):
    fig,axes=plt.subplots(1,3,figsize=(10.5,3.2),sharex=True)
    for ax,month in zip(axes,['2022-05','2022-06','2022-07']):
        lead=cache[month]['prediction_matches'].lead_minutes
        ax.hist(lead,bins=np.arange(10,100,10),color=PRED,edgecolor='white')
        ax.axvline(lead.median(),ls='--',color='#A56715',lw=1.2)
        ax.set_title(f'{pd.Timestamp(month).strftime("%B")}: n={len(lead)}, median={lead.median():g} min',fontsize=9)
        ax.set_xlim(10,90);ax.set_xticks([10,30,50,70,90]);ax.set_xlabel('Lead time (min)')
    axes[0].set_ylabel('Matched predictions')
    fig.suptitle('Lead times from confirmed alert issuance to NOAA peak',fontsize=12,color=FLUX)
    fig.tight_layout();save_figure(fig,path,dpi=200);plt.close(fig)


def write_notes(root,metrics,coverage):
    notes='''# Implementation choices and replication limits

This is a reconstruction of the supplied manuscript's main causal wavelet method. The old April code is not the manuscript implementation. No parameter was selected to fit published April counts or improve May-July results.

## Fixed manuscript settings

- Raw linear GOES XRS-B 1-8 angstrom flux, 1-minute cadence, one copy per duplicate timestamp.
- db2 DWT, level-3 detail energy (sum of squared cD3 coefficients), right-aligned 30-minute window.
- Decisions every 2 minutes, anchored at each month's 00:00 UTC.
- Trailing 6-hour quantiles: Q80 Prediction, Q95 Detection. Initial 120 minutes excluded from alerts/evaluation.
- Four elapsed minutes of above-threshold observations before issuing an alert. Same-stream alerts separated by no more than 12 minutes are merged.
- C/M/X NOAA reference peaks only; no model-derived labels.
- Prediction: chronological greedy one-to-one matching to the earliest unused NOAA peak 10-90 minutes after alert issuance, inclusive.
- Detection: chronological greedy one-to-one matching to the closest unused NOAA peak within +/-10 minutes, inclusive. Distance ties choose the earlier peak, then event ID.
- Month-level precision, recall and F1. Prediction lead quartiles use exactly the same TP pairs.
- A display-only percentile-rank priority is fixed at the confirmed event start. Priority never selects matches or changes alerts.

## Choices the manuscript does not completely specify

| Issue | Main implementation | Additional record/check |
|---|---|---|
| 'Two consecutive decision intervals (4 min)' | Requires elapsed 4 minutes: above threshold at t, t+2 and t+4; issues at t+4 | Two positive decisions, issued at t+2, are scored separately |
| Alert start vs persistence confirmation | Main `start_time` is actual confirmation/issuance; no backdating | `crossing_start_time` is retained; retrospectively scoring it is a separate sensitivity case |
| Short-gap linear interpolation vs no future information | Backfill at most 2 missing minutes only when the right endpoint arrives; never issue a decision at an unobserved right edge | Every filled sample has an `available_at` timestamp; prefix and future-perturbation tests passed |
| DWT boundary mode | PyWavelets symmetric extension, using only values inside the past/current 30-minute window; this matches the supplied code's default | Mode is explicitly recorded in configuration.json |
| Quantile estimator and current feature | NumPy linear quantile on finite decision-time features in inclusive [t-360,t], including current feature | Initial 120-minute warm-up permits a partially filled history |
| Warm-up and month boundaries | Independent monthly initialization; first 120 minutes excluded; no daily resets | Monthly matching uses NOAA peaks in the same UTC month; boundary opportunities can be truncated |
| Quality flags and unavailable windows | Nonfinite/negative flux is unavailable. Finite flagged data is retained because the paper gives no flag filter. Any unavailable feature window resets alert continuity and prevents merging across that gap | All gaps and finite flagged minutes are reported |
| Reference events during outages | All C/M/X peaks after warm-up remain in the denominator; data gaps withhold decisions, rather than silently deleting labels | Missing GOES flux at the exact NOAA peak is flagged separately |
| Threshold equality | Strictly greater than the threshold opens/continues an event; equal or lower closes it | The comparison is fixed in code |
| Baseline comparison | No SMA baseline result is claimed | The original SMA window, adaptive rule and April parameter grid are absent from the supplied materials |

The sensitivity cases are declared interpretations, not a search for the best score. Use `confirmed_4min` as the main result. Never pool or select the highest sensitivity score as though it were a single preregistered run.

## April audit

The published paper reports 122 NOAA C/M/X events, 167 Prediction alerts / 35 TP, and 101 Detection alerts / 34 TP. The official complete SWPC April archive contains 224 C/M/X peaks. This reconstruction produces 247 Prediction alerts / 86 TP and 116 Detection alerts / 69 TP. Its 39-minute Prediction median does not establish replication: the reference population, alerts and matched pairs differ.

The original April label catalog, exclusions and executable manuscript implementation are needed to reproduce the published tables exactly. The manuscript's SMA baseline cannot be reproduced from its reported scores alone.

## Data and evaluation scope

The supplied GOES CSV has four identical XRS-B/quality-flag rows per minute. One copy is retained after verifying equality. The spacecraft identity is not established by the CSV filename; the NOAA reference observatory is retained, including G17 reports.

No NOAA C/M/X peaks fall inside the initial 120-minute warm-up in these four months. The May-July reference counts therefore remain 257, 107 and 166. July includes one peak with missing GOES flux at the exact minute; it remains a reference event. NOAA event numbers reused for distinct peaks are kept separate.

Monthly resets and restricting matches to the same month are fixed for every run. A Prediction near month end can be scored as FP even if an out-of-month peak would have followed within 90 minutes. This boundary convention is not fully specified in the paper and is stated here instead of hidden.
'''
    (root/'METHOD_NOTES.md').write_text(notes)
    readme='''# Solar-flare manuscript extension: May, June and July 2022

The main causal workflow has been executed on the supplied 2022 GOES XRS-B data and independently evaluated against NOAA SWPC C/M/X peaks. April is a reconstruction check. These results are not a verified reproduction of the original paper's April tables; see METHOD_NOTES.md.

## Open these files first

- Solar_Flare_Manuscript_Extension_Report.pdf: results, methods, April comparison, sensitivity and scientific figures.
- monthly_metrics.csv: full April/May/June/July Prediction and Detection counts, precision, recall, F1 and lead statistics.
- pooled_May_June_July_metrics.csv: TP/FP/FN pooled across the three extension months, with metrics recomputed from counts.
- prediction_lead_statistics.csv: quartiles and ranges over exactly the matched Prediction pairs.
- prediction_onset_audit.csv and prediction_onset_summary.csv: separate pre-start warnings from warnings during a flare but before its peak.
- sensitivity_metrics.csv: explicitly labeled alternate interpretations of persistence and event start.
- validation_results.json: numerical, causality, matching and count-identity checks.
- METHOD_NOTES.md: fixed paper parameters, reconstructed details and remaining replication limits.

Each months/YYYY-MM folder contains raw/processed minute flux, features and trailing thresholds at every decision, independent NOAA references, Prediction/Detection event tables, matched pairs, false positives, false negatives, data gaps and daily counts. figures/daily contains all 92 May-July daily plots. figures contains month plots and performance/lead figures.

`daily_counts.csv` keeps alert-date and peak-date TP counts separate because a matched pair can cross midnight. Month-level TP is unambiguous. Daily figures show the number of alert starts and NOAA peaks in that UTC day.

## Reproduce the results

Python 3.12 was used. Create an environment and install code/requirements.txt. From this folder:

```bash
python code/run_manuscript_pipeline.py --goes data/GOES_XRSB_April_July_2022.csv --noaa noaa/catalogs/NOAA_XRA_context_2022_03_31_to_08_01.csv --out rerun
python code/validate_manuscript_pipeline.py --results rerun --code code/run_manuscript_pipeline.py
python code/build_manuscript_deliverables.py --results rerun
```

The compact CSV retains original raw minute flux and flags after duplicate removal. You can instead pass the original GOES_2022_FULL.zip to --goes. Metrics are unchanged; the input-row metadata naturally differs because the compact CSV already has one row per minute.

NOAA original reports, URLs, checksums and format documentation are under noaa. New alerts do not use NOAA labels, future flux, daily global thresholds or future-derived flare classes. Code and CSVs preserve UTC timestamps and exact counts; displayed report scores are rounded to three decimals.

The main algorithm's parameters are frozen from the manuscript. The two sensitivity interpretations are not selected as replacements based on their scores. The original SMA baseline grid was not supplied, so no baseline score is invented.
'''
    (root/'README.md').write_text(readme)


def make_report(root,metrics,coverage,lead_stats):
    regular=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    bold=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    if not regular.exists() or not bold.exists():
        fonts=Path(matplotlib.get_data_path())/'fonts'/'ttf'
        regular=fonts/'DejaVuSans.ttf'
        bold=fonts/'DejaVuSans-Bold.ttf'
    pdfmetrics.registerFont(TTFont('Research',str(regular)))
    pdfmetrics.registerFont(TTFont('ResearchBold',str(bold)))
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ResearchBody',fontName='Research',fontSize=9,leading=13,spaceAfter=7,textColor=colors.HexColor('#25344A')))
    styles.add(ParagraphStyle(name='ResearchTitle',fontName='ResearchBold',fontSize=20,leading=25,spaceAfter=10,textColor=colors.HexColor(FLUX)))
    styles.add(ParagraphStyle(name='ResearchHead',fontName='ResearchBold',fontSize=12,leading=16,spaceBefore=10,spaceAfter=7,textColor=colors.HexColor(FLUX)))
    styles.add(ParagraphStyle(name='ResearchSmall',fontName='Research',fontSize=7.8,leading=11,spaceAfter=6,textColor=colors.HexColor('#536277')))
    def p(s,style='ResearchBody'):return Paragraph(s,styles[style])
    def table(rows,widths,font=8):
        converted=[[p(str(c),'ResearchSmall') if isinstance(c,str) and len(c)>36 else c for c in row] for row in rows]
        t=Table(converted,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'Research'),('FONTSIZE',(0,0),(-1,-1),font),
                              ('FONTNAME',(0,0),(-1,0),'ResearchBold'),('BACKGROUND',(0,0),(-1,0),colors.HexColor(FLUX)),
                              ('TEXTCOLOR',(0,0),(-1,0),colors.white),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                              ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#EEF2F7')]),
                              ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
                              ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
                              ('LINEBELOW',(0,0),(-1,0),.5,colors.white)]))
        return t
    doc=SimpleDocTemplate(str(root/'Solar_Flare_Manuscript_Extension_Report.pdf'),pagesize=A4,
                          rightMargin=38,leftMargin=38,topMargin=38,bottomMargin=37)
    width=A4[0]-76;story=[]
    extension=metrics.loc[metrics.month.ne('2022-04')]
    story += [p('Solar-flare prediction and detection','ResearchTitle'),p('May, June and July 2022. Manuscript reconstruction using the supplied GOES data and official NOAA C/M/X references.','ResearchSmall')]
    story += [p('The main causal wavelet workflow has been run for all three months. It uses the paper’s fixed parameters and separately scores Prediction and Detection. The original April results are not reproduced: the paper’s NOAA event selection and some implementation details remain unavailable.')]
    story += [p('Prediction results','ResearchHead')]
    rows=[['Month','Alerts','NOAA','TP','FP','FN','Precision','Recall','F1']]
    for r in extension.loc[extension.stream.eq('prediction')].to_dict('records'):
        rows.append([r['month'][5:],'{}'.format(r['alerts_issued']),r['noaa_cmx_events'],r['TP'],r['FP'],r['FN'],f"{r['precision']:.3f}",f"{r['recall']:.3f}",f"{r['F1']:.3f}"])
    col=[44,45,45,35,35,35,75,70,width-384]
    story.append(table(rows,col))
    story += [p('Detection results','ResearchHead')]
    rows=[['Month','Alerts','NOAA','TP','FP','FN','Precision','Recall','F1']]
    for r in extension.loc[extension.stream.eq('detection')].to_dict('records'):
        rows.append([r['month'][5:],r['alerts_issued'],r['noaa_cmx_events'],r['TP'],r['FP'],r['FN'],f"{r['precision']:.3f}",f"{r['recall']:.3f}",f"{r['F1']:.3f}"])
    story.append(table(rows,col))
    story += [p('Matched Prediction lead times','ResearchHead')]
    rows=[['Month','n = TP','Q1 (min)','Median (min)','Q3 (min)','Range (min)']]
    for r in lead_stats.loc[lead_stats.month.ne('pooled')].to_dict('records'):
        rows.append([r['month'][5:],r['n'],f"{r['Q1']:.2f}",f"{r['median']:.1f}",f"{r['Q3']:.2f}",f"{r['min']:g}-{r['max']:g}"])
    story.append(table(rows,[50,60,90,100,90,width-390]))
    pool=pd.read_csv(root/'pooled_May_June_July_metrics.csv')
    pr=pool.loc[pool.stream.eq('prediction')].iloc[0];de=pool.loc[pool.stream.eq('detection')].iloc[0]
    story += [Spacer(1,10),p(f'Pooled over 530 NOAA peaks: Prediction {int(pr.TP)} TP / {int(pr.FP)} FP / {int(pr.FN)} FN, F1 {pr.F1:.3f}. Detection {int(de.TP)} TP / {int(de.FP)} FP / {int(de.FN)} FN, F1 {de.F1:.3f}. Pooled scores are calculated from total counts, not averaged monthly scores.')]
    story += [p('Main timing convention: simulated streaming alerts are issued after four elapsed minutes of persistence. Prediction matches use 10-90 minutes from issuance to NOAA peak; Detection uses +/-10 minutes. Scores shown to three decimals.','ResearchSmall'),PageBreak()]
    story += [p('Causal processing and evaluation','ResearchTitle')]
    setting_rows=[['Stage','Fixed method'],['Input','Original linear XRS-B flux; one identical timestamp copy; 1-minute grid.'],
                  ['Feature','db2 level-3 detail energy on [t-29,t]. No log transform or smoothing.'],
                  ['Decision/threshold','Every 2 minutes. Q80 and Q95 over finite features in inclusive [t-360,t].'],
                  ['Initialization','Separate monthly state. First 120 minutes excluded. Partly filled 6-hour history is permitted after warm-up.'],
                  ['Persistence/merging','Above threshold at t, t+2 and t+4; confirmed at t+4. Same-stream gaps <=12 minutes merge; unavailable feature windows break continuity.'],
                  ['Matching','Chronological greedy 1:1. Prediction selects minimum eligible lead. Detection selects minimum absolute peak offset.'],
                  ['Priority','Percentile rank at confirmed start, fixed thereafter; affects display only.']]
    story.append(table(setting_rows,[115,width-115],font=8))
    story += [p('Resolving the paper’s timing ambiguities','ResearchHead'),
              p('The text combines “two consecutive decisions” with “4 min.” At a two-minute cadence, two positive timestamps are only two minutes apart. The main reconstruction enforces four elapsed minutes and issues at the third positive decision. A two-positive-decision alternative is also recorded.'),
              p('The initial crossing and actual issuance are different timestamps. Main metrics use the confirmed issuance time. The crossing timestamp is retained and evaluated only as a retrospective sensitivity case. Earlier crossing-based leads must not be described as advance warnings that had already been issued.'),
              p('Linear interpolation needs a right endpoint. Missing runs of at most two minutes are backfilled only when that observed endpoint arrives. Each filled sample records its availability time, and no alert is issued at an unobserved current minute. Longer gaps and windows containing unresolved samples are masked.'),
              p('PyWavelets symmetric boundary extension acts only inside the already available 30-minute window. The quantile method is explicitly linear and includes the current feature. These details were not fully specified in the manuscript and are recorded in configuration.json.'),
              p('Reference scope and boundaries','ResearchHead'),
              p('All C/M/X peaks after warm-up remain in the denominator, including outages. There are no NOAA C/M/X peaks in the initial 120 minutes of these four months. Matching uses peaks in the same UTC month; month-boundary opportunities can therefore be truncated. Finite samples with nonzero quality flags are retained because the paper supplies no flag filter.'),PageBreak()]
    story += [p('April verification and sensitivity','ResearchTitle'),p('The reconstructed April result differs from the published tables. The same 39-minute median is insufficient evidence of replication: the event population and matched pairs are different.')]
    rows=[['Quantity','Paper April','Reconstructed April']]
    ap=metrics.loc[metrics.month.eq('2022-04')&metrics.stream.eq('prediction')].iloc[0]
    ad=metrics.loc[metrics.month.eq('2022-04')&metrics.stream.eq('detection')].iloc[0]
    for name,a,b in [('NOAA C/M/X peaks',122,224),('Prediction issued / TP / FP / FN','167 / 35 / 132 / 87',f'{int(ap.alerts_issued)} / {int(ap.TP)} / {int(ap.FP)} / {int(ap.FN)}'),
                     ('Prediction precision / recall / F1','0.210 / 0.287 / 0.242',f'{ap.precision:.3f} / {ap.recall:.3f} / {ap.F1:.3f}'),
                     ('Prediction median lead (min)',39,ap.lead_median_minutes),('Detection issued / TP / FP / FN','101 / 34 / 67 / 88',f'{int(ad.alerts_issued)} / {int(ad.TP)} / {int(ad.FP)} / {int(ad.FN)}'),
                     ('Detection precision / recall / F1','0.337 / 0.279 / 0.305',f'{ad.precision:.3f} / {ad.recall:.3f} / {ad.F1:.3f}')]:rows.append([name,a,b])
    story.append(table(rows,[205,147,width-352],font=8))
    story += [p('Prediction sensitivity: event timing changes the matched pairs','ResearchHead')]
    sens=pd.read_csv(root/'sensitivity_metrics.csv')
    rows=[['Month','Main F1 / lead','Crossing F1 / lead','Two decisions F1 / lead']]
    for month in ['2022-05','2022-06','2022-07']:
        main=metrics.loc[metrics.month.eq(month)&metrics.stream.eq('prediction')].iloc[0]
        onset=sens.loc[sens.month.eq(month)&sens.stream.eq('prediction')&sens.run.eq('initial_crossing_retrospective')].iloc[0]
        two=sens.loc[sens.month.eq(month)&sens.stream.eq('prediction')&sens.run.eq('two_positive_decisions')].iloc[0]
        rows.append([month[5:],f'{main.F1:.3f} / {main.lead_median_minutes:g} min',f'{onset.F1:.3f} / {onset.lead_median_minutes:g} min',f'{two.F1:.3f} / {two.lead_median_minutes:g} min'])
    story.append(table(rows,[45,155,155,width-355],font=8))
    story += [p('These are separate interpretations, not tuned replacements. Moving the match timestamp also changes eligible greedy pairs, so pooled medians need not shift by exactly four minutes. All Detection sensitivities are supplied in the CSV files.','ResearchSmall'),
              p('Data availability','ResearchHead')]
    rows=[['Month','Missing minutes','Filled minutes','Decision coverage','Missing peak flux']]
    for r in coverage.loc[coverage.month.ne('2022-04')].to_dict('records'):
        rows.append([r['month'][5:],r['raw_missing_flux_minutes'],r['interpolated_missing_minutes'],f"{100*r['eligible_decision_coverage_after_warmup']:.2f}%",r['noaa_peaks_missing_GOES_flux']])
    story.append(table(rows,[45,105,95,155,width-400],font=8))
    story += [Spacer(1,8),p('Exact April replication requires the original NOAA catalog/exclusions and executable manuscript implementation. The SMA baseline window, adaptive rule and April search grid were not supplied, so the baseline comparison is not reproduced.'),PageBreak()]
    story += [p('Performance and lead distributions','ResearchTitle'),
              Image(str(root/'figures/monthly_performance.png'),width=width,height=width*3.6/10.5),
              Spacer(1,8),Image(str(root/'figures/prediction_lead_histograms.png'),width=width,height=width*3.2/10.5),
              Spacer(1,10),p('Detection precision exceeds Prediction precision in all three months. Prediction produces many false alarms: 583 of 802 merged issued alerts are unmatched under the fixed 10-90-minute NOAA peak rule. A long successful warning lead does not imply a high chance that any given alert will match a flare.'),
              p('The matched Prediction lead distributions contain exactly 101 May, 46 June and 72 July TP pairs. They exclude false positives. They are conditional lead statistics, rather than lead estimates for every issued warning.'),
              p('Of the 219 matched Predictions, 198 precede NOAA’s reported flare start. The other 21 occur at or after the reported start but before the peak. The manuscript’s peak-matching protocol therefore does not by itself demonstrate forecasting of flare onset. See prediction_onset_audit.csv for every pair.'),
              p('Validation completed','ResearchHead'),p('Independent recalculation checked wavelet windows, trailing thresholds and all monthly count identities. An independent greedy matcher reproduced every matched pair. Truncated prefixes and 1000-fold changes to future flux left earlier decisions and alert starts unchanged. Boundary matching and interpolation-availability tests passed.'),PageBreak()]
    for month in ['2022-05','2022-06','2022-07']:
        refs=pd.read_csv(root/'months'/month/'noaa_reference_events.csv')
        busy=refs.peak_time.str[:10].value_counts().sort_values(ascending=False)
        day=sorted(busy[busy.eq(busy.max())].index)[0]
        name=pd.Timestamp(month).strftime('%B %Y')
        story += [p(f'{name}: month and daily timelines','ResearchTitle'),
                  p(f'The month view shows all alerts and NOAA peaks. The example day ({day}) has the highest NOAA C/M/X peak count in this month ({int(busy.max())}). It is selected by reference activity, not model score. All daily plots are included.','ResearchSmall'),
                  Image(str(root/'figures'/f'{month}_timeline.png'),width=width,height=width*6.3/12),Spacer(1,8),
                  Image(str(root/'figures/daily'/month/f'{day}.png'),width=width,height=width*6.3/12),PageBreak()]
    story += [p('Files, provenance and use','ResearchTitle'),
              p('The package contains runnable Python code, the raw minute XRS-B subset, original NOAA reports, event catalogs, configuration, features, thresholds, alerts, matched pairs, false positives, false negatives, sensitivity results, data gaps and all daily figures.'),
              p('Use monthly_metrics.csv for exact numerical results and METHOD_NOTES.md for implementation choices. The report rounds scores to three decimals. The code never reads NOAA labels while generating features or alerts; labels enter only the subsequent evaluation.'),
              p('Monthly run state resets once, at the UTC month start. There are no daily threshold resets. The four source rows per minute have identical flux and quality flags; one copy is retained after equality checks.'),
              p('The GOES CSV filename does not establish satellite identity. NOAA report observatories are preserved, including G17 records. Check original spacecraft provenance before making satellite-specific claims.'),
              p('How to describe these results','ResearchHead'),p('Use: “We extended the manuscript’s stated causal wavelet method to May-July 2022 using fixed settings and independently evaluated alerts against the full NOAA SWPC C/M/X catalog. Implementation choices absent from the manuscript were documented and tested in sensitivity analyses. The original April results were not exactly reproduced.”'),
              p('Do not claim that the published April tables, hidden reference subset or SMA baseline have been replicated. The original code and labels are necessary to resolve those issues.'),
              p('Sources and versions','ResearchHead'),
              p('User-supplied sources: GOES_2022_FULL.zip; Detection_and_Short_Term_Prediction_of_Solar_Flares_ACDSA2027 (2)(1).pdf; Aprflare with code.pdf. The latter implements a different method and was used only for comparison.'),
              p('NOAA SWPC edited solar-event archive (2022):<br/>https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/solar_event_reports/2022/','ResearchSmall'),
              p('Official NOAA event-format documentation:<br/>https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/solar_event_reports/docs/SolarEventReport.pdf','ResearchSmall'),
              p('PyWavelets DWT documentation:<br/>https://pywavelets.readthedocs.io/en/latest/ref/dwt-discrete-wavelet-transform.html','ResearchSmall'),
              p('NumPy quantile documentation:<br/>https://numpy.org/doc/stable/reference/generated/numpy.quantile.html','ResearchSmall'),
              p('Runtime: Python 3.12.14; NumPy 2.3.5; pandas 2.2.3; PyWavelets 1.8.0; matplotlib 3.10.8. Source-file SHA-256 checksums and validation records are included. NOAA reports were retrieved September 30, 2026.','ResearchSmall')]
    def footer(canvas,doc):
        canvas.setFont('Research',7);canvas.setFillColor(colors.HexColor('#64748B'))
        canvas.drawString(38,22,'Solar-flare extension - manuscript reconstruction')
        canvas.drawRightString(A4[0]-38,22,str(doc.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--skip-daily',action='store_true')
    args=parser.parse_args();root=args.results.resolve()
    assert json.loads((root/'validation_results.json').read_text())['status']=='passed'
    metrics=pd.read_csv(root/'monthly_metrics.csv');coverage=pd.read_csv(root/'data_coverage.csv')
    figures=root/'figures';figures.mkdir(exist_ok=True)
    cache={month:load_month(root,month) for month in ['2022-05','2022-06','2022-07']}
    lead_rows=[];all_leads=[];onset_audits=[];onset_summaries=[]
    for month,data in cache.items():
        start=pd.Timestamp(month+'-01',tz='UTC');stop=start+pd.offsets.MonthBegin(1)
        timeline_figure(data,start,stop,figures/f'{month}_timeline.png',f'{pd.Timestamp(month).strftime("%B %Y")}: causal alerts and NOAA peaks',True)
        if not args.skip_daily:
            for day in pd.date_range(start,stop,freq='D',inclusive='left'):
                timeline_figure(data,day,day+pd.Timedelta(days=1),figures/'daily'/month/f'{day:%Y-%m-%d}.png',f'{day:%Y-%m-%d}: causal alerts and NOAA peaks')
            print('Rendered every daily plot for',month,flush=True)
        lead=data['prediction_matches'].lead_minutes.to_numpy();all_leads.extend(lead)
        qs=np.quantile(lead,[0,.25,.5,.75,1])
        lead_rows.append(dict(month=month,n=len(lead),min=qs[0],Q1=qs[1],median=qs[2],Q3=qs[3],max=qs[4]))
        source=read_csv(root/'months'/month/'noaa_reference_events.csv',['start_time'])
        onset=data['prediction_matches'].merge(source[['event_id','start_time']].rename(columns={'start_time':'noaa_start_time'}),on='event_id',validate='one_to_one')
        onset['onset_lead_minutes']=(onset.noaa_start_time-onset.alert_start_time).dt.total_seconds()/60
        onset['before_noaa_start']=onset.onset_lead_minutes.gt(0)
        onset['month']=month;onset_audits.append(onset)
        onset_summaries.append({'month':month,'matched_predictions':len(onset),'before_noaa_start':int(onset.before_noaa_start.sum()),
                                'at_or_after_noaa_start':int((~onset.before_noaa_start).sum()),
                                'median_onset_lead_minutes_all_matches':float(onset.onset_lead_minutes.median())})
    qs=np.quantile(all_leads,[0,.25,.5,.75,1]);lead_rows.append(dict(month='pooled',n=len(all_leads),min=qs[0],Q1=qs[1],median=qs[2],Q3=qs[3],max=qs[4]))
    lead_stats=pd.DataFrame(lead_rows);lead_stats.to_csv(root/'prediction_lead_statistics.csv',index=False)
    pd.concat(onset_audits,ignore_index=True).to_csv(root/'prediction_onset_audit.csv',index=False,date_format='%Y-%m-%dT%H:%M:%SZ')
    pd.DataFrame(onset_summaries).to_csv(root/'prediction_onset_summary.csv',index=False)
    performance_figure(metrics,figures/'monthly_performance.png');lead_figure(cache,figures/'prediction_lead_histograms.png')
    write_notes(root,metrics,coverage);make_report(root,metrics,coverage,lead_stats)
    print('Saved report, scientific figures, lead statistics and method notes.',flush=True)


if __name__=='__main__':main()
