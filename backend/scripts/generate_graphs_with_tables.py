"""Build the evidence-backed IEEE figure and companion PDF; no new model calls."""
from pathlib import Path
import csv, json, math, statistics, hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'research_evaluation/data'
OUT = ROOT / 'paper_graphs/graphs_with_tables'
OUT.mkdir(parents=True, exist_ok=True)
def read_csv(name):
    with (DATA / name).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))
runs = read_csv('transcription_runs.csv')
saved = read_csv('transcription_summary.csv')
summary = []
for s in saved:
    duration = int(s['duration_s'])
    selected = [r for r in runs if int(r['duration_s']) == duration]
    times = [float(r['transcription_s']) for r in selected]
    row = dict(duration=duration, n=len(times), mean=statistics.mean(times), sd=statistics.stdev(times), rtf=statistics.mean(times)/duration)
    assert len(times) == int(s['n']) == 3
    for key, field in [('mean','mean_s'),('sd','sd_s'),('rtf','mean_rtf')]:
        assert math.isclose(row[key], float(s[field]), rel_tol=1e-10)
    for r in selected:
        assert math.isclose(float(r['real_time_factor']),float(r['transcription_s'])/duration,rel_tol=1e-10)
        assert hashlib.sha256((DATA/r['prediction_file']).read_bytes()).hexdigest() == r['prediction_sha256']
    summary.append(row)
summary.sort(key=lambda r:r['duration'])
pairs = read_csv('consistency_pairs.csv')
provenance = json.loads((DATA/'consistency_provenance.json').read_text())
for item in provenance:
    assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest() == item['sha256']
for r in pairs:
    assert math.isclose(float(r['jaccard']),int(r['intersection'])/int(r['union']),rel_tol=1e-10,abs_tol=1e-10)

plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':8,'axes.labelsize':8,'xtick.labelsize':7,'ytick.labelsize':7,'pdf.fonttype':42,'ps.fonttype':42})
fig, ax = plt.subplots(figsize=(3.5,2.55))
fig.subplots_adjust(left=.16,right=.97,bottom=.20,top=.96)
x=[r['duration'] for r in summary]
y=[r['mean'] for r in summary]
sd=[r['sd'] for r in summary]
ax.errorbar(x,y,yerr=sd,fmt='o-',color='black',markerfacecolor='white',markersize=4,linewidth=1,capsize=3,elinewidth=.8)
ax.set(xlabel='Input audio duration (s)',ylabel='Transcription time (s)',xticks=x,ylim=(0,14),xlim=(20,130))
ax.set_yticks(range(0,15,2))
ax.grid(axis='y',linewidth=.4,color='.85')
ax.spines[['top','right']].set_visible(False)
for ext in ['pdf','svg','png']:
    fig.savefig(OUT/f'fig_1_transcription_latency.{ext}',dpi=600)
plt.close(fig)

# Restore the existing RTF graph, with uncertainty derived from recorded repeats.
fig, ax = plt.subplots(figsize=(3.5,2.55))
fig.subplots_adjust(left=.19,right=.97,bottom=.20,top=.95)
positions = list(range(len(summary)))
rtf = [r['rtf'] for r in summary]
rtf_sd = [r['sd']/r['duration'] for r in summary]
ax.bar(positions,rtf,yerr=rtf_sd,width=.55,color='white',edgecolor='black',hatch='///',capsize=3,error_kw={'elinewidth':.8})
ax.set(xlabel='Input audio duration (s)',ylabel='Real-time factor',xticks=positions,xticklabels=[str(r['duration']) for r in summary],ylim=(0,.13))
ax.set_yticks([0,.025,.05,.075,.10,.125])
ax.grid(axis='y',linewidth=.4,color='.85')
ax.set_axisbelow(True)
ax.spines[['top','right']].set_visible(False)
for pos, value, error in zip(positions,rtf,rtf_sd):
    ax.text(pos,value+error+.004,f'{value:.3f}',ha='center',va='bottom',fontsize=7)
for ext in ['pdf','svg','png']:
    fig.savefig(OUT/f'fig_2_real_time_factor.{ext}',dpi=600)
plt.close(fig)

# Empty evaluation layouts: missing measurements must never be plotted as zero.
from matplotlib.patches import Rectangle
labels=['Action','Decision','Question','Discussion','Information']
for number, name in [(3,'confusion_matrix'),(4,'rouge_comparison'),(5,'extraction_ablation')]:
    fig,ax=plt.subplots(figsize=(5.5,3.3))
    fig.subplots_adjust(left=.19,right=.97,bottom=.26,top=.82)
    fig.suptitle('EVALUATION TEMPLATE - NO MEASURED RESULTS',fontsize=10,fontweight='bold',y=.97)
    if number==3:
        ax.set_xlim(-.5,4.5); ax.set_ylim(4.5,-.5)
        for row in range(5):
            for col in range(5):
                ax.add_patch(Rectangle((col-.5,row-.5),1,1,facecolor='white',edgecolor='.65',linewidth=.5))
                ax.text(col,row,'N/A',ha='center',va='center',color='.45',fontsize=8)
        ax.set_xticks(range(5),labels,rotation=25,ha='right')
        ax.set_yticks(range(5),labels)
        ax.set_xlabel('Predicted class'); ax.set_ylabel('True class')
    else:
        groups=['Lead-3','TextRank','MMR','BART'] if number==4 else ['Full system','Without grounding','Without reconciliation']
        ax.set_xlim(-.5,len(groups)-.5); ax.set_ylim(0,1)
        ax.set_xticks(range(len(groups)),groups,rotation=20,ha='right')
        ax.set_ylabel('ROUGE F1 score' if number==4 else 'Extraction score')
        ax.set_xlabel('Summarization method' if number==4 else 'Pipeline configuration')
        ax.text(.5,.55,'Awaiting evaluation data\nNo bars plotted; missing values are not zero',transform=ax.transAxes,ha='center',va='center',fontsize=10,bbox=dict(facecolor='white',edgecolor='.7',pad=8))
        ax.grid(axis='y',color='.9',linewidth=.5)
        ax.spines[['top','right']].set_visible(False)
    for ext in ['pdf','svg','png']:
        fig.savefig(OUT/f'fig_{number}_{name}_TEMPLATE.{ext}',dpi=600)
    plt.close(fig)

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='DocTitle',fontName='Times-Bold',fontSize=20,leading=24,spaceAfter=8))
styles.add(ParagraphStyle(name='SectionTitle',fontName='Times-Bold',fontSize=12,leading=15,spaceBefore=10,spaceAfter=6))
styles.add(ParagraphStyle(name='Text',fontName='Times-Roman',fontSize=10,leading=14,spaceAfter=7))
styles.add(ParagraphStyle(name='Cap',fontName='Times-Roman',fontSize=9,leading=12,spaceBefore=5,spaceAfter=7))
styles.add(ParagraphStyle(name='Cell',fontName='Times-Roman',fontSize=9,leading=11))
styles.add(ParagraphStyle(name='SmallText',fontName='Times-Roman',fontSize=8.5,leading=11,spaceAfter=5))
story=[]
def p(text,style='Text'):
    story.append(Paragraph(text,styles[style]))
def section(text): p(text,'SectionTitle')
def table(headers,rows,widths):
    data=[[Paragraph('<b>'+escape(str(c))+'</b>',styles['Cell']) for c in headers]]
    data += [[Paragraph(escape(str(c)),styles['Cell']) for c in row] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='CENTER')
    t.setStyle(TableStyle([('LINEABOVE',(0,0),(-1,0),.8,colors.black),('LINEBELOW',(0,0),(-1,0),.5,colors.black),('LINEBELOW',(0,-1),(-1,-1),.8,colors.black),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story.append(t)
    story.append(Spacer(1,8))

p('graphs with tables','DocTitle')
p('IEEE paper insertion guide | Verified existing measurements | 2 November 2026','SmallText')
p('All five requested graph types are covered. Figs. 1-2 contain verified measurements. Figs. 3-5 are explicitly labeled evaluation templates with no numerical results; they must be populated and validated before submission. Three measured-results tables and three template tables are included. Figure and table numbers below are provisional and should follow the final manuscript order.')
section('1. Transcription efficiency')
p('<b>Where to add:</b> Results and Analysis, in a subsection titled "Transcription Efficiency", after the hardware/model configuration and timing protocol. Insert Fig. 1 followed by Table I. The graph is exported at 3.5-inch single-column width; use the vector PDF in the manuscript.')
story.append(Image(str(OUT/'fig_1_transcription_latency.png'),width=3.5*inch,height=2.55*inch))
caption='Fig. 1. Warm transcription latency of Faster-Whisper base under CPU/int8 execution for 30-, 60-, and 120-s clips from one source recording. Markers show the mean of three repeated runs; error bars denote one sample standard deviation. Model loading and downstream NLP are excluded. Connecting lines guide the eye.'
p(caption,'Cap')
p('TABLE I. WARM TRANSCRIPTION LATENCY','Cap')
rows=[[r['duration'],r['n'],f"{r['mean']:.3f}",f"{r['sd']:.3f}"] for r in summary]
table(['Audio (s)','Runs','Mean time (s)','SD (s)'],rows,[90,65,140,125])
p('<b>Table note:</b> SD uses n - 1 in the denominator. Repeated runs estimate timing variability, not variability across independent meetings.','SmallText')
p('<b>Paper-ready explanation:</b> Mean warm-transcription time increased from 2.315 s for a 30-s clip to 11.562 s for a 120-s clip. Mean RTF ranged from 0.077 to 0.096, below the real-time threshold of 1.0 for all tested durations. These observations describe the tested CPU/int8 configuration and one recording; they do not establish corpus-wide scaling or end-to-end meeting-analysis latency.')

story.append(PageBreak())
p('Real-time factor','DocTitle')
section('2. Processing time relative to audio duration')
p('<b>Where to add:</b> Results and Analysis, in the same "Transcription Efficiency" subsection immediately after the latency result. Use Fig. 2 with Table II, or combine Figs. 1-2 as two labeled panels if the conference page limit is tight.')
story.append(Image(str(OUT/'fig_2_real_time_factor.png'),width=3.5*inch,height=2.55*inch))
p('Fig. 2. Mean real-time factor (RTF) for Faster-Whisper base under CPU/int8 execution, calculated as warm-transcription time divided by input audio duration. Bars represent three runs per duration; error bars denote one sample standard deviation. All clips originate from one recording. Lower values indicate faster processing; the real-time threshold is 1.0 (outside the displayed range).','Cap')
p('TABLE II. REAL-TIME FACTOR FOR THE EXISTING TRANSCRIPTION BENCHMARK','Cap')
table(['Audio (s)','Runs','Mean RTF','SD of RTF'],[[r['duration'],r['n'],f"{r['rtf']:.4f}",f"{r['sd']/r['duration']:.4f}"] for r in summary],[90,65,140,125])
p('<b>Table note:</b> RTF is dimensionless. For each fixed clip duration d, mean RTF = mean time / d and SD of RTF = SD of time / d. This is a normalized view of the same nine runs shown in Fig. 1, not an independent experiment.','SmallText')
p('<b>Paper-ready explanation:</b> Mean RTF values were 0.0772, 0.0952, and 0.0963 for the 30-, 60-, and 120-s clips, respectively. Thus, warm transcription consumed approximately 7.7-9.6% of the corresponding audio duration on the tested configuration. The measurements support faster-than-real-time transcription for these clips; they do not establish real-time behavior of the full NLP pipeline.')
p('<b>Why retain both figures:</b> Latency conveys absolute waiting time, while RTF makes the relation to audio length explicit. They share the same measurements and should not be described as separate validation datasets. RTF has been restored so that both existing performance graphs are available for manuscript insertion.')

story.append(PageBreak())
p('Consistency results and paper placement','DocTitle')
section('3. Re-analysis consistency: use a table')
p('<b>Where to add:</b> Results and Analysis, under "Re-analysis Consistency", following the definition of Jaccard overlap and the description of the unchanged input/model/prompt configuration. Keep this result as Table III; flat count curves and 100% bars add little information.')
p('TABLE III. CORE INSIGHT COUNTS AND MINIMUM AGREEMENT WITH RUN 1','Cap')
core=[('action_items','Actions'),('decisions','Decisions'),('questions','Questions')]
consistency_rows=[]
for category,label in core:
    fresh=sorted([r for r in pairs if r['stage']=='Fresh candidates' and r['category']==category],key=lambda r:int(r['run']))
    persisted=sorted([r for r in pairs if r['stage']=='Persisted' and r['category']==category],key=lambda r:int(r['run']))
    assert [int(r['run']) for r in fresh] == [2,3,4,5]
    assert len(persisted)==4
    counts=[int(fresh[0]['reference_count'])]+[int(r['run_count']) for r in fresh]
    assert counts == [int(persisted[0]['reference_count'])]+[int(r['run_count']) for r in persisted]
    consistency_rows.append([label,*counts,f"{min(float(r['jaccard']) for r in fresh):.2f}",f"{min(float(r['jaccard']) for r in persisted):.2f}"])
table(['Category','R1','R2','R3','R4','R5','Min J, fresh','Min J, saved'],consistency_rows,[80,32,32,32,32,32,90,90])
p('<b>Table note:</b> Counts match for fresh candidates and saved reports. Each minimum is calculated over R2-R5 compared with R1 (four comparisons), not all ten run pairs. J = intersection / union for recorded item sets. Values describe one short English meeting fixture and five fresh calls, not cache hits.','SmallText')
p('<b>Paper-ready explanation:</b> All five fresh analyses produced two actions, one decision, and one question for the evaluated fixture. Minimum recorded Jaccard agreement with Run 1 was 1.00 for each core category in both fresh candidates and saved reports. This demonstrates consistency for this fixture, rather than extraction accuracy or a guarantee of deterministic model output on arbitrary meetings. Topic labels varied and are excluded from the core-category claim.')
section('What the consistency result does and does not establish')
p('Agreement compares outputs with one another; it does not compare them with human ground truth. A stable output can still contain errors. The existing audit also records unchanged candidate counts through validation and persistence; that retention result is not a component-ablation experiment.')
p('Do not add a zero-shot baseline bar from the draft unless its original measured outputs and matching procedure can be verified. Do not describe unchanged counts alone as proof of semantic equality. The table above uses the recorded item-overlap data in addition to counts.')
section('Suggested manuscript sequence')
p('Experimental Setup: source recording, clip lengths, CPU/model configuration, warm-up and repeated-run protocol. Results: Figs. 1-2 with Tables I-II for efficiency, then Table III for consistency. For a tight page limit, combine the two efficiency figures as panels (a) and (b) and consolidate their tables. Discussion: single-recording and single-fixture limitations. Keep the existing system architecture diagram in Methodology; it is not an evaluation graph.')

# Include all remaining proposed graphs as unmeasured, visibly marked templates.
templates=[
(3,'Dialogue-act confusion matrix','confusion_matrix','IV',
'Classification Performance, after the held-out test-set description.',
'Fig. 3 (evaluation template; no measured results). Planned confusion matrix for five dialogue-act classes. Rows denote reference labels and columns denote predicted labels. N/A cells are missing measurements, not zero counts.',
['True / predicted','Action','Decision','Question','Discussion','Information'],
[[label]+['N/A']*5 for label in labels],[95,62,62,62,75,75],
'Use human-labeled test sentences from meetings excluded from training. Fit TF-IDF and the classifier on training data only; retain meeting IDs to prevent train/test leakage. Count each true/predicted label pair. If normalized, divide each row by its support and state the convention.',
'The diagonal will show correct predictions; off-diagonal cells will show class confusions. No class-performance conclusion can be drawn until test predictions are available. The saved classifier and training_sentences.csv alone do not establish an unseen test evaluation.'),
(4,'Summarization quality comparison','rouge_comparison','V',
'Summarization Evaluation, after the reference-summary and scoring protocol.',
'Fig. 4 (evaluation template; no measured results). Planned grouped comparison of ROUGE-1, ROUGE-2, and ROUGE-L F1 across summarization methods on the same held-out meetings. No bars are drawn because verified scores are unavailable.',
['Method','ROUGE-1 F1','ROUGE-2 F1','ROUGE-L F1'],
[[name,'N/A','N/A','N/A'] for name in ['Lead-3','TextRank','MMR','BART']],[135,95,95,105],
'Collect human-written reference summaries and outputs for each implemented method on the same meetings. Fix summary-length limits, tokenizer, stemming and scorer version. Compute per-meeting scores, then report their mean and uncertainty across meetings; do not treat individual sentences as independent meetings.',
'ROUGE compares textual overlap with references; it does not verify factual correctness. Interpret differences only after evaluation. Include a method only if it actually ran under the reported protocol; draft-only scores are not used here.'),
(5,'Extraction component ablation','extraction_ablation','VI',
'Ablation Study, after the description of the extraction metric and component configurations.',
'Fig. 5 (evaluation template; no measured results). Planned precision, recall, and F1 comparison for the full pipeline and versions with grounding or reconciliation disabled separately. No bars are drawn because controlled measurements are unavailable.',
['Configuration','Precision','Recall','F1'],
[[name,'N/A','N/A','N/A'] for name in ['Full system','Without grounding','Without reconciliation']],[185,80,80,85],
'Annotate gold action items, owners and deadlines for held-out meetings, and define one-to-one prediction/reference matching before scoring. Keep inputs, model, prompt and sampling settings fixed; disable one component per variant. For reconciliation, use repeated analyses of the same inputs and also report item agreement and edit preservation.',
'An ablation can attribute changes to a component only under matched experimental conditions. Existing retention counts are not precision/recall or component-ablation measurements. Report each variant with the same averaging convention and sample size.')]
for number,title,name,roman,placement,caption,headers,rows,widths,protocol,explanation in templates:
    story.append(PageBreak())
    p(title,'DocTitle')
    p('<b>STATUS: EVALUATION TEMPLATE - NOT AN EXPERIMENTAL RESULT.</b> N/A means not measured. Do not insert this template into the submitted paper as a result.','SmallText')
    p('<b>Where to add after evaluation:</b> Results and Analysis / '+placement)
    story.append(Image(str(OUT/f'fig_{number}_{name}_TEMPLATE.png'),width=5.5*inch,height=3.3*inch))
    p(caption,'Cap')
    p('TABLE '+roman+'. '+title.upper()+' (TEMPLATE; NOT MEASURED)','Cap')
    table(headers,rows,widths)
    p('<b>Required evaluation:</b> '+protocol,'SmallText')
    p('<b>How to explain the completed graph:</b> '+explanation,'SmallText')

story.append(PageBreak())
p('Selection rationale and reproducibility','DocTitle')
section('Status of all five originally proposed graphs')
table(['Original proposal','Final status'],[
['1. Transcription latency','Included as Fig. 1 and Table I; verified timing measurements.'],
['2. Real-time factor','Included as Fig. 2 and Table II; calculated from the same verified timings.'],
['3. Classification confusion matrix','Included as Fig. 3 / Table IV templates. Requires held-out true labels and model predictions.'],
['4. ROUGE comparison','Included as Fig. 4 / Table V templates. Requires reference summaries and reproducible scores.'],
['5. Extraction component ablation','Included as Fig. 5 / Table VI templates. Requires annotated meetings and controlled component removal.']],[145,300])
p('Figs. 3-5 are visibly marked empty evaluation templates, not experimental results. Their N/A table entries are missing data, not zeros. No numerical values have been invented. Constant consistency/retention curves remain excluded because Table III communicates the verified core consistency result more clearly. The unverified baseline Jaccard comparison remains excluded.','SmallText')
section('Measurement protocol and source files')
env=json.loads((DATA/'benchmark_environment.json').read_text())
p('The existing benchmark uses Faster-Whisper base, CPU/int8, beam size 5, VAD enabled (500-ms minimum silence), automatic language detection, and a 30-s warm-up. Three clip durations from one source recording were each timed three times. Warm timing includes decoding, VAD, language detection, consuming generated segments, and output construction; it excludes model loading, clip writing, NLP, and persistence.')
for text in [
'Timing inputs: research_evaluation/data/transcription_runs.csv and transcription_summary.csv.',
'Configuration: research_evaluation/data/benchmark_environment.json.',
'Consistency inputs: research_evaluation/data/consistency_pairs.csv and consistency_provenance.json; contextual interpretation: REANALYSIS_CONSISTENCY_REPORT.md.',
'Generation checks: means, sample SDs and RTFs independently recomputed from all nine timed runs; prediction-file hashes and ten consistency-artifact hashes verified; recorded overlap ratios checked against intersection/union counts.',
'No new inference or accuracy experiments were run. Numerical checks establish internal consistency of saved measurements, not independent replication of the benchmark.'
]: p(escape(text),'SmallText')
section('Deliverables and formatting')
p('Python source: backend/scripts/generate_graphs_with_tables.py. Standalone figures in paper_graphs/graphs_with_tables/: fig_1_transcription_latency.pdf and fig_2_real_time_factor.pdf contain measured results; fig_3_confusion_matrix_TEMPLATE.pdf, fig_4_rouge_comparison_TEMPLATE.pdf and fig_5_extraction_ablation_TEMPLATE.pdf are empty layouts. All have SVG and 600-dpi PNG alternatives. Figures use grayscale-safe styling, labeled axes, and embedded TrueType fonts in PDF. Tables use horizontal rules and captions above; the figure caption appears below.')
p('Apply the destination conference template and renumber all figures/tables on insertion. This companion PDF is an insertion guide, not a replacement two-column manuscript. Avoid repeating Table I in full if page limits favor showing RTF only in the results text.')
p('Formatting reference: <link href="https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-graphics-for-your-article/resolution-and-size/" color="blue">IEEE Author Center: Resolution and Size</link>.','SmallText')

def footer(canvas,doc):
    canvas.setFont('Times-Roman',8)
    canvas.drawString(42,25,'graphs with tables | Meeting Analyzer | IEEE paper companion')
    canvas.drawRightString(A4[0]-42,25,str(doc.page))
output=ROOT/'graphs with tables.pdf'
doc=SimpleDocTemplate(str(output),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=36,bottomMargin=42,title='graphs with tables',author='Meeting Analyzer')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
(OUT/'verification.json').write_text(json.dumps({'timed_runs':len(runs),'summary_recomputed':True,'prediction_hashes_verified':9,'consistency_hashes_verified':len(provenance),'overlap_ratios_checked':len(pairs),'figure_count':5,'measured_figures':2,'template_figures':3,'table_count':6,'measured_tables':3,'template_tables':3,'pdf':str(output)},indent=2))
print(output)
print('Verified nine timing runs, prediction hashes, ten consistency hashes, and overlap ratios.')
