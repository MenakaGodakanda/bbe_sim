#!/usr/bin/env python3
"""Draws every figure of the BBE paper in one run.

Usage:
    python make_all_figures.py --csv path/to/E6_by_dst_chain.csv --out figures

Needs: numpy, pandas, matplotlib   (pip install numpy pandas matplotlib)
The six diagram figures need no data. The per-chain figure needs the file
E6_by_dst_chain.csv written by the simulation; without --csv it is skipped.
Output: PNG files at 300 dpi in the --out directory (default ./figures).
"""
import argparse, os
import numpy as np
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch

ap = argparse.ArgumentParser()
ap.add_argument("--csv", default=None, help="path to E6_by_dst_chain.csv (per-chain figure only)")
ap.add_argument("--out", default="figures", help="output directory (default: ./figures)")
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
OUT = os.path.join(args.out, "")

RED="#b03a2e"; BLUE="#1f618d"; GREY="#566573"; GREEN="#1e8449"; AMBER="#b9770e"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":8})

def box(ax,x,y,w,h,fc,ec,lw=1.2,r=1.2,ls="-"):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle=f"round,pad=0,rounding_size={r}",fc=fc,ec=ec,lw=lw,ls=ls))
def arrow(ax,a,b,color=GREY,ls="-",lw=1.1,ms=9):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle="-|>",mutation_scale=ms,color=color,lw=lw,ls=ls))

# ============ Figure A: threat model ============
fig,ax=plt.subplots(figsize=(7.4,5.0)); ax.set_xlim(0,100); ax.set_ylim(-17,64); ax.axis("off")
box(ax,0.5,56,99,7,"#fef9e7",AMBER,r=1)
ax.text(50,59.5,"Threat: every wrongly flagged user may be refused service or reported, so the attacker wants\nmany flagged users for a small budget",ha="center",va="center",fontsize=7.6,color="#7e5109")
box(ax,0.5,22,22,30,"#fdedec",RED); ax.text(11.5,48.5,"Attacker",ha="center",weight="bold",color=RED,fontsize=9.5)
ax.text(11.5,43,"holds tainted value\n(budget B)",ha="center",va="top",fontsize=7.6)
ax.text(11.5,33,"pays a fee c\nper transfer",ha="center",va="top",fontsize=7.6)
box(ax,37,8,27,44,"#eaf2f8",BLUE); ax.text(50.5,48.5,"Innocent users",ha="center",weight="bold",color=BLUE,fontsize=9.5)
ys=[42,34,26,18,11.5]; labs=["clean balance $12","clean balance $30","clean balance $250","clean balance $900","many more accounts"]
for y,l in zip(ys,labs):
    ax.add_patch(Circle((41.5,y),1.9,fc="white",ec=BLUE,lw=1.2)); ax.text(45,y,l,va="center",fontsize=7.2)
    arrow(ax,(22.8,37),(39.3,y),color=RED,lw=0.9,ms=7)
ax.text(30.5,46.5,"dust d",color=RED,fontsize=7.8,style="italic",ha="center")
ax.text(50.5,5.5,"victims cannot refuse incoming transfers",ha="center",fontsize=7.4,style="italic",color=BLUE)
box(ax,77.5,22,22,30,"#eafaf1",GREEN); ax.text(88.5,48.5,"Defender",ha="center",weight="bold",color=GREEN,fontsize=9.5)
ax.text(88.5,43,"AML screening\nfollows taint",ha="center",va="top",fontsize=7.6)
ax.text(88.5,33,"flags an account\nwhen its rule fires",ha="center",va="top",fontsize=7.6)
arrow(ax,(64.5,30),(77,34),color=GREEN,ls="--"); ax.text(70.8,35.8,"flag?",color=GREEN,fontsize=7.6,style="italic",ha="center")
ax.text(50,-0.8,"Cost to the attacker of flagging one victim under each policy",ha="center",fontsize=8,weight="bold",color=GREY)
cards=[("Poison","any contact flags the user","cost per victim ≈ c","so reach ≈ B / c",RED),
       ("Share rule (θ = 10%)","flags if taint ≥ 10% of balance","cost per victim ≈ balance / 9 + c","cheap for low balances",AMBER),
       ("BBE","flags if taint ≥ δ and ≥ 10%","cost per victim ≥ δ + c","so at most B / (δ + c) flagged",GREEN)]
for i,(t,a,b,c,col) in enumerate(cards):
    x0=0.5+i*33.4; box(ax,x0,-16.5,32.2,13.5,"white",col)
    ax.text(x0+16.1,-5.4,t,ha="center",weight="bold",color=col,fontsize=8.2)
    ax.text(x0+16.1,-8.6,a,ha="center",fontsize=7); ax.text(x0+16.1,-11.4,b,ha="center",fontsize=7); ax.text(x0+16.1,-14.2,c,ha="center",fontsize=7,style="italic")
fig.savefig(OUT+"fig_threat_model.png",dpi=300,bbox_inches="tight",facecolor="white"); plt.close(fig)

# ============ Figure B: flag regions and cost per victim ============
th=0.1; delta=100; c=0.05
B=np.logspace(0,5,400)
fig,(a1,a2)=plt.subplots(1,2,figsize=(7.4,3.5))
share_line=th/(1-th)*B
a1.fill_between(B,np.maximum(share_line,delta),1e6,color=GREEN,alpha=0.25,lw=0,label="flagged by BBE")
a1.fill_between(B,share_line,np.maximum(share_line,delta),where=(share_line<delta),color=RED,alpha=0.25,lw=0,label="flagged by share rule, spared by BBE")
a1.plot(B,share_line,color=AMBER,lw=1.3,label="share rule: T = θB/(1−θ)")
a1.axhline(delta,color=GREEN,lw=1.3,ls="--",label="floor δ = 100")
a1.set_xscale("log"); a1.set_yscale("log"); a1.set_xlim(1,1e5); a1.set_ylim(0.1,1e5)
a1.set_xlabel("victim's clean balance B (USD)"); a1.set_ylabel("tainted amount T received (USD)")
a1.set_title("(a) Which victims are flagged",fontsize=8.5); a1.legend(fontsize=6.4,loc="upper left",frameon=True,facecolor="white",framealpha=1,edgecolor="#d5d8dc")
a1.annotate("floor stops binding\nabove B = 900",xy=(900,100),xytext=(4000,1.5),fontsize=6.6,ha="left",arrowprops=dict(arrowstyle="-",lw=0.6,color=GREY))
poison=np.full_like(B,1e-6+c); share=share_line+c; bbe=np.maximum(delta,share_line)+c
a2.plot(B,poison,color=RED,lw=1.4,label="poison"); a2.plot(B,share,color=AMBER,lw=1.4,label="share rule"); a2.plot(B,bbe,color=GREEN,lw=1.6,label="BBE (δ = 100)")
a2.axvline(29.5,color=GREY,lw=0.9,ls=":"); a2.text(31,2e4,"median observed\nbalance $29.5",fontsize=6.4,color=GREY,va="top")
a2.set_xscale("log"); a2.set_yscale("log"); a2.set_xlim(1,1e5); a2.set_ylim(1e-2,1e5)
a2.set_xlabel("victim's clean balance B (USD)"); a2.set_ylabel("attacker's cost to flag one victim (USD)")
a2.set_title("(b) What the attacker must pay",fontsize=8.5); a2.legend(fontsize=6.6,loc="center right",bbox_to_anchor=(1.0,0.36),frameon=False)
fig.tight_layout(); fig.savefig(OUT+"fig_flag_regions.png",dpi=300,facecolor="white"); plt.close(fig)

# ============ Figure C: case study ============
rec=[250.12,249.92,250.37,247.65]; cum=np.cumsum(rec); lab=["1st receipt\n17 Dec","2nd receipt\n+2.4 h","3rd receipt\n+2.9 h","4th receipt\n25 Dec (+8 d)"]
dust={"share":cum[0]/9,"bbe":100.0}
exp_share=[dust["share"]/(cum[i]+dust["share"])*100 for i in range(4)]
exp_bbe=[dust["bbe"]/(cum[i]+dust["bbe"])*100 for i in range(4)]
flag_share=[e>=10-1e-9 for e in exp_share]; flag_bbe=[(dust["bbe"]>=100) and e>=10 for e in exp_bbe]
fig,(a1,a2)=plt.subplots(1,2,figsize=(7.4,3.5),gridspec_kw={"width_ratios":[1,1.25]})
x=np.arange(4); a1.bar(x,rec,bottom=np.r_[0,cum[:-1]],color="#aed6f1",ec=BLUE,lw=0.8,width=0.72)
for i in range(4): a1.text(i,cum[i]-rec[i]/2,f"+{rec[i]:.2f}",ha="center",va="center",fontsize=6.4)
a1.set_xticks(x); a1.set_xticklabels(lab,fontsize=6.3); a1.set_ylabel("clean balance after receipt (USD)"); a1.set_title("(a) A real account, four receipts",fontsize=8.5)
a1.text(0.02,0.97,"Dust sent right after the 1st receipt:\npoison \\$0.000001 · share rule \\$27.79 · BBE \\$100",transform=a1.transAxes,fontsize=6.4,va="top",color=RED)
a1.set_ylim(0,1250)
a2.axhline(10,color=GREY,lw=1,ls="--"); a2.text(-0.45,12.5,"θ = 10%",fontsize=6.5,color=GREY,ha="left")
a2.plot(x,[100]*4,color=RED,lw=1.4,marker="o",label="poison (whole balance tainted)")
a2.plot(x,exp_share,color=AMBER,lw=1.4,marker="o",label="share rule, dust \\$27.79")
a2.plot(x,exp_bbe,color=GREEN,lw=1.6,marker="o",label="BBE, floor \\$100, dust \\$100")
for xs,ys,fl,col in [(x,[100]*4,[True]*4,RED),(x,exp_share,flag_share,AMBER),(x,exp_bbe,flag_bbe,GREEN)]:
    for xi,yi,f in zip(xs,ys,fl): a2.plot(xi,yi,"o",ms=6.5,mfc=(col if f else "white"),mec=col,zorder=5)
for xi,yi in zip(x,exp_share): a2.text(xi,yi-7.5,f"{yi:.1f}%",fontsize=6.2,color=AMBER,ha="center")
for xi,yi in zip(x,exp_bbe): a2.text(xi,yi+4.5,f"{yi:.1f}%",fontsize=6.2,color=GREEN,ha="center")
a2.set_xticks(x); a2.set_xticklabels(lab,fontsize=6.3); a2.set_xlim(-0.5,3.5); a2.set_ylim(-14,112); a2.set_ylabel("tainted share of balance (%)")
a2.set_title("(b) Exposure after the dust (filled = flagged)",fontsize=8.5); a2.legend(fontsize=6.2,loc="center right",bbox_to_anchor=(1.0,0.62),frameon=False)
fig.tight_layout(); fig.savefig(OUT+"fig_case_study.png",dpi=300,facecolor="white"); plt.close(fig)

# ============ Figure D: real-world validation ============
fig,ax=plt.subplots(figsize=(7.4,5.4)); ax.set_xlim(0,100); ax.set_ylim(-3,63); ax.axis("off")
ax.text(50,61,"Public record of the Tornado Cash litigation",ha="center",weight="bold",fontsize=8.6,color=GREY)
ax.plot([4,96],[54,54],color=GREY,lw=1.6)
ev=[(6,"Aug 2022","Tornado Cash\nsanctioned"),(26,"Oct 2022","Coin Center complaint:\ndusting alleged"),(52,"26 Nov 2024","Van Loon, 5th Cir.:\nsmart contracts not\n“property”"),(72,"21 Mar 2025","Treasury removes\nTornado Cash from list"),(92,"3 Jul 2025","11th Cir. ends the\nCoin Center appeal")]
for xx,d,t in ev:
    ax.plot(xx,54,"o",ms=7,color=BLUE,zorder=5); ax.text(xx,57.3,d,ha="center",fontsize=7.3,weight="bold",color=BLUE)
    ax.text(xx,50.8,t,ha="center",va="top",fontsize=6.6)
box(ax,2,36,96,7,"#fdedec",RED,r=1); ax.text(50,39.2,"No court decided the dusting allegation: the case is used as documented evidence\nof the problem, not as legal precedent",ha="center",va="center",fontsize=7.2,color=RED)
heads=[("Alleged in the complaint",RED),("What BBE does about it",GREEN),("Evidence in this paper",BLUE)]
xs=[2,35,68]
for (h,col),x0 in zip(heads,xs):
    box(ax,x0,29,30,4.6,"white",col); ax.text(x0+15,31.3,h,ha="center",va="center",weight="bold",color=col,fontsize=7.6)
rows=[("Users cannot refuse\nunsolicited transfers","Threat model assumes dust\ncannot be refused","Section 3.1"),
      ("“Dusted” users may face\nliability or reporting","Contact alone does not flag:\nneeds T ≥ δ and T ≥ θB","1,000 USD budget flags\n19,999 accounts (poison)\nbut ≤ 9 (BBE), Section 4.3"),
      ("Courts scrutinise what\ncan be sanctioned","Explicit thresholds (δ, θ) that\nanyone can recompute","Section 3.3, Table 8")]
for r,(a,b,c_) in enumerate(rows):
    y0=19.5-r*9.6
    for (t,x0,col) in [(a,2,RED),(b,35,GREEN),(c_,68,BLUE)]:
        box(ax,x0,y0,30,8,"#f8f9f9",col,lw=0.9); ax.text(x0+15,y0+4,t,ha="center",va="center",fontsize=6.9)
    arrow(ax,(32.1,y0+4),(34.9,y0+4),ms=9); arrow(ax,(65.1,y0+4),(67.9,y0+4),ms=9)
fig.savefig(OUT+"fig_validation.png",dpi=300,bbox_inches="tight",facecolor="white"); plt.close(fig)
print("done")

# ============ Overview of the method ============
fig,ax=plt.subplots(figsize=(7.4,5.4)); ax.set_xlim(0,100); ax.set_ylim(0,72); ax.axis("off")
box(ax,2,62,96,9,"#fef9e7",AMBER)
ax.text(50,68.2,"Research question",ha="center",weight="bold",color="#7e5109",fontsize=8.6)
ax.text(50,64.4,"How many innocent accounts can an attacker with budget B get flagged under each taint policy,\nand how much genuine tainted value does the BBE floor let escape?",ha="center",va="center",fontsize=6.9)
# analytical
box(ax,2,31,43,26,"#eaf2f8",BLUE); ax.text(23.5,54,"Analytical part (Sections 3.2 to 3.5)",ha="center",weight="bold",color=BLUE,fontsize=8.2)
for i,t in enumerate(["Taint policies: poison, haircut, FIFO","BBE rule: flag if T ≥ δ and T ≥ θB","Theorem 1: flags ≤ B / (δ + c)","Link inference, ambiguity k, threshold π"]):
    ax.text(4.5,49.3-i*4.6,"•  "+t,fontsize=7.4,va="center")
# empirical
box(ax,55,31,43,26,"#eafaf1",GREEN); ax.text(76.5,54,"Empirical part (Sections 3.9 and 4)",ha="center",weight="bold",color=GREEN,fontsize=8.2)
for i,t in enumerate(["Real Wormhole ledger: 250,527 transfers","E1 linking · E2 leverage · E3 replay","E4 visibility · E5 case · E6 chains","Sensitivity analyses S1 to S6"]):
    ax.text(57.5,49.3-i*4.6,"•  "+t,fontsize=7.4,va="center")
arrow(ax,(45.3,44),(54.7,44),ms=9); arrow(ax,(54.7,40.5),(45.3,40.5),ms=9)
ax.text(50,36.0,"closed form\nchecked by\nreplay",ha="center",va="center",fontsize=6.3,color=GREY,style="italic")
arrow(ax,(23.5,61.7),(23.5,57.3),color=GREY); arrow(ax,(76.5,61.7),(76.5,57.3),color=GREY)
# verification
box(ax,2,22,43,6.5,"white",GREY,ls="--",r=1); ax.text(23.5,25.2,"Verification tests (Section 3.8): synthetic cases,\nnever used for reported results",ha="center",va="center",fontsize=6.9,color=GREY)
arrow(ax,(23.5,28.7),(23.5,30.7),color=GREY,ls="--",ms=8)
# answers
ax.text(70,22.2,"What answers the research question",ha="center",weight="bold",color=GREY,fontsize=8.0)
cards=[("Part 1: protection","E2, E3: accounts flagged\nper budget (Sections 4.3, 4.4)",RED),("Part 2: price","E1, E4: link ambiguity and tainted\nvalue below the floor (4.2, 4.5)",AMBER),("Validation and relevance","Case study (4.8), court case\n(4.10), SDG relevance",BLUE)]
for i,(t,s_,col) in enumerate(cards):
    x0=2+i*33; box(ax,x0,2,30.5,13,"white",col)
    ax.text(x0+15.25,12.1,t,ha="center",weight="bold",color=col,fontsize=7.8); ax.text(x0+15.25,6.8,s_,ha="center",va="center",fontsize=6.9)
ax.plot([93,93],[31.0,19.0],color=GREEN,lw=1.1)
ax.plot([17.25,93],[19.0,19.0],color=GREEN,lw=1.1)
for xx in (17.25,50.25,83.25): arrow(ax,(xx,19.0),(xx,15.3),color=GREEN,ms=8)
fig.savefig(OUT+"fig_overview.png",dpi=300,bbox_inches="tight",facecolor="white"); plt.close(fig)

# ============ Bridge-link ambiguity diagram ============
fig,ax=plt.subplots(figsize=(7.4,4.8)); ax.set_xlim(0,100); ax.set_ylim(0,66); ax.axis("off")
box(ax,2,36,23,28,"#fdedec",RED); ax.text(13.5,60.2,"Deposit",ha="center",weight="bold",color=RED,fontsize=9)
ax.text(13.5,54.5,"source chain\n1,000 tainted USD\ntoken T to chain D\ntime t",ha="center",va="top",fontsize=7.2)
box(ax,30,36,42,28,"#eaf2f8",BLUE); ax.text(51,60.2,"Matching withdrawals",ha="center",weight="bold",color=BLUE,fontsize=8.6)
ax.text(51,56.6,"same token and chain, time within Δ,\namount within fee φ",ha="center",va="center",fontsize=6.4,color=GREY)
for i in range(20):
    r,cidx=divmod(i,10); cx=35.2+cidx*3.55; cy=50.8-r*5.0
    ax.add_patch(Circle((cx,cy),1.35,fc="white" if i else "#f5b7b1",ec=BLUE if i else RED,lw=1.1))
ax.text(51,38.6,"k = 20 candidates (the red one is the true link)",ha="center",fontsize=6.8,style="italic",color=BLUE)
arrow(ax,(25.3,50),(29.7,50),color=RED)
ax.text(86,60.2,"Ambiguity set",ha="center",weight="bold",color=GREY,fontsize=8.6)
ax.text(86,54.5,"The defender cannot\ntell which candidate\nreceived the deposit",ha="center",va="top",fontsize=7,color=GREY)
rows=[("Copying linker",RED,"each of the 20 receivers is\nmarked tainted with 1,000 USD","20,000 USD of taint created;\n20 victims flagged"),
      ("Conserving linker",AMBER,"each receiver gets x / k =\n1,000 / 20 = 50 USD","50 USD is below the floor\nδ = 100 USD: none flagged"),
      ("Conserving linker\nwith π = 0.5",GREEN,"link weight 1 / k = 0.05\nis below π: link not followed","no taint is passed on:\nnone flagged")]
for i,(t,col,a_,b_) in enumerate(rows):
    y0=27.0-i*10.4
    box(ax,2,y0-4.3,96,9.2,"white",col,r=1)
    ax.text(4,y0+0.3,t,weight="bold",color=col,fontsize=7.6,va="center")
    ax.text(30,y0+0.3,a_,fontsize=6.8,va="center"); arrow(ax,(58.5,y0+0.3),(62,y0+0.3),color=col,ms=8); ax.text(63.5,y0+0.3,b_,fontsize=6.8,va="center")
fig.savefig(OUT+"fig_linking_ambiguity.png",dpi=300,bbox_inches="tight",facecolor="white"); plt.close(fig)


if args.csv is None:
    print("No --csv given: per-chain figure skipped.")
else:
    # ============ Per-chain chart ============
    d=pd.read_csv(args.csv)
    if "name" not in d.columns: d["name"]=np.nan
    d=d[d.n_transfers>=1000].copy(); d["name"]=d.name.fillna(d.dst_chain.astype(int).astype(str))
    d=d.iloc[::-1]; y=np.arange(len(d)); h=0.26
    fig,(a1,a2)=plt.subplots(1,2,figsize=(7.4,4.4),gridspec_kw={"width_ratios":[1.25,1]},sharey=True)
    a1.barh(y+h,d.poison,height=h,color=RED,label="poison"); a1.barh(y,d.share,height=h,color=AMBER,label="share rule"); a1.barh(y-h,d.bbe_floor100,height=h,color=GREEN,label="BBE (δ = 100)")
    a1.axvline(9,color=GREEN,ls=":",lw=1); a1.set_xscale("log"); a1.set_xlim(5,4e4)
    a1.set_yticks(y); a1.set_yticklabels([f"{n}\n(median ${m:,.0f})" for n,m in zip(d.name,d.median_balance_usd)],fontsize=6.6)
    a1.set_xlabel("accounts flagged (budget 1,000 USD)"); a1.set_title("(a) Leverage by destination chain",fontsize=8.5); h_,l_=a1.get_legend_handles_labels()
    cols=[RED if n=="Moonbeam" else BLUE for n in d.name]
    a2.barh(y,d.mean_k,height=0.55,color=cols); a2.set_xscale("log"); a2.set_xlim(0.3,900)
    for yi,k_,u in zip(y,d.mean_k,d.share_unique): a2.text(k_*1.12,yi,f"{k_:.2f}  ({u*100:.0f}% unique)",va="center",fontsize=6.2)
    a2.set_xlabel("mean candidates per deposit, k"); a2.set_title("(b) Link ambiguity by chain",fontsize=8.5); a2.axvline(1,color=GREY,ls=":",lw=1)
    fig.legend(h_,l_,loc="lower center",ncol=3,fontsize=7,frameon=False); fig.tight_layout(rect=(0,0.05,1,1)); fig.savefig(OUT+"fig_per_chain.png",dpi=300,facecolor="white"); plt.close(fig)
    print("done")

print("Figures written to", os.path.abspath(args.out))
