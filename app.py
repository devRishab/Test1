from pathlib import Path
import textwrap, zipfile, os

root = Path("/mnt/data/futures_trading_lab")
root.mkdir(exist_ok=True)

app = r'''
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="Futures Trading Learning Lab", page_icon="📈", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 3rem;}
div[data-testid="stMetric"] {background: rgba(120,120,120,.08); border: 1px solid rgba(120,120,120,.18); padding: 14px; border-radius: 12px;}
.small-note {font-size:.9rem; opacity:.75}
</style>
""", unsafe_allow_html=True)

def money(x): return f"₹{x:,.2f}"
def theoretical_future(S, r, q, u, y, T):
    return S * np.exp((r - q + u - y) * T)

def pnl(position, entry, current, lot, contracts):
    direction = 1 if position == "Long" else -1
    return direction * (current-entry) * lot * contracts

st.title("📈 Futures Trading Learning Lab")
st.caption("Interactive educational simulator for futures pricing, P&L, margin, basis, convergence, arbitrage, hedging and risk.")

with st.sidebar:
    st.header("Global Market Inputs")
    asset = st.text_input("Underlying asset", "NIFTY 50 (Simulated)")
    category = st.selectbox("Asset category", ["Equity Index", "Stock", "Commodity", "Currency", "Interest Rate"])
    spot = st.number_input("Spot price", min_value=0.01, value=22500.0, step=10.0)
    entry = st.number_input("Entry futures price", min_value=0.01, value=22600.0, step=10.0)
    current_fut = st.number_input("Current futures price", min_value=0.01, value=22800.0, step=10.0)
    position = st.radio("Position", ["Long", "Short"], horizontal=True)
    lot = st.number_input("Lot size", min_value=1, value=50)
    contracts = st.number_input("Contracts", min_value=1, value=2)
    expiry = st.date_input("Expiry date", value=date.today()+timedelta(days=45), min_value=date.today())
    r_pct = st.slider("Risk-free rate (%)", 0.0, 20.0, 7.0, 0.1)
    q_pct = st.slider("Dividend yield (%)", 0.0, 10.0, 1.2, 0.1)
    u_pct = st.slider("Storage cost (%)", 0.0, 20.0, 0.0, 0.1)
    y_pct = st.slider("Convenience yield (%)", 0.0, 20.0, 0.0, 0.1)
    learning = st.toggle("Learning Mode", value=True)

days = max((expiry-date.today()).days, 0)
T = days/365
r,q,u,y = [v/100 for v in (r_pct,q_pct,u_pct,y_pct)]
fair = theoretical_future(spot,r,q,u,y,T)
gross_pnl = pnl(position,entry,current_fut,lot,contracts)
notional = current_fut*lot*contracts
basis = spot-current_fut
mispricing = current_fut-fair

tabs = st.tabs(["Overview","Trade Simulator","Fair Value & Basis","Arbitrage Lab","Margin & MTM","Hedging","Scenarios & Risk","Learning Lab"])

with tabs[0]:
    st.subheader(f"{asset} — Simulated Data")
    c = st.columns(6)
    c[0].metric("Spot", money(spot))
    c[1].metric("Current Futures", money(current_fut), money(current_fut-entry))
    c[2].metric("Days to Expiry", days)
    c[3].metric("Position P&L", money(gross_pnl))
    c[4].metric("Basis (S−F)", f"{basis:,.2f}")
    c[5].metric("Fair Value Gap", money(mispricing))
    st.info("Educational simulator only. Simulated results are not investment advice.")
    x = np.linspace(entry*.85, entry*1.15, 101)
    long_p = (x-entry)*lot*contracts
    short_p = -long_p
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x,y=long_p,name="Long futures payoff"))
    fig.add_trace(go.Scatter(x=x,y=short_p,name="Short futures payoff"))
    fig.add_vline(x=entry, line_dash="dash", annotation_text="Entry / Break-even")
    fig.add_hline(y=0, line_dash="dot")
    fig.update_layout(title="Futures Payoff at Settlement", xaxis_title="Settlement price", yaxis_title="Profit / Loss (₹)", height=470)
    st.plotly_chart(fig, use_container_width=True)
    if learning:
        st.success("Learning insight: A futures contract creates linear exposure. The long gains when futures prices rise above entry; the short gains when they fall.")

with tabs[1]:
    st.subheader("Position Calculator")
    tc = st.number_input("Total transaction costs (₹)", min_value=0.0, value=500.0)
    net = gross_pnl-tc
    margin_pct = st.slider("Initial margin (% of notional)", 1.0, 50.0, 12.0, .5)
    margin = notional*margin_pct/100
    rom = net/margin*100 if margin else 0
    move_pct = (current_fut-entry)/entry*100
    leverage = notional/margin if margin else 0
    a,b,c,d = st.columns(4)
    a.metric("Gross P&L", money(gross_pnl))
    b.metric("Net P&L", money(net))
    c.metric("Return on Margin", f"{rom:.2f}%")
    d.metric("Effective Leverage", f"{leverage:.2f}×")
    st.write(f"Futures price move since entry: **{move_pct:.2f}%**")
    if learning:
        sign = "+" if position=="Long" else "−"
        st.code(f"P&L = {sign}(Current Futures − Entry Futures) × Lot Size × Contracts\n"
                f"    = {sign}({current_fut:,.2f} − {entry:,.2f}) × {lot} × {contracts}\n"
                f"    = {gross_pnl:,.2f}")
        st.warning("Leverage magnifies both gains and losses because margin is only a fraction of the contract's notional exposure.")

with tabs[2]:
    st.subheader("Cost-of-Carry Fair Value")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Theoretical Futures", money(fair))
    c2.metric("Market Futures", money(current_fut))
    c3.metric("Mispricing", money(mispricing))
    c4.metric("Mispricing %", f"{mispricing/fair*100:.3f}%")
    st.latex(r"F_0=S_0e^{(r-q+u-y)T}")
    rates = np.linspace(max(0,r-.05),r+.05,60)
    vals = [theoretical_future(spot,rr,q,u,y,T) for rr in rates]
    fig = go.Figure(go.Scatter(x=rates*100,y=vals))
    fig.update_layout(title="Fair Value Sensitivity to Interest Rate",xaxis_title="Risk-free rate (%)",yaxis_title="Theoretical futures price")
    st.plotly_chart(fig,use_container_width=True)

    st.subheader("Basis and Convergence Simulation")
    n=max(days,10)
    t=np.arange(n+1)
    rng=np.random.default_rng(7)
    spot_path=spot*np.exp(np.cumsum(rng.normal(0,0.006,n+1)))
    initial_gap=current_fut-spot
    fut_path=spot_path + initial_gap*(1-t/n)
    conv=pd.DataFrame({"Day":t,"Spot":spot_path,"Futures":fut_path})
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=conv.Day,y=conv.Spot,name="Spot"))
    fig.add_trace(go.Scatter(x=conv.Day,y=conv.Futures,name="Futures"))
    fig.update_layout(title="Simulated Spot–Futures Convergence",xaxis_title="Days elapsed",yaxis_title="Price")
    st.plotly_chart(fig,use_container_width=True)
    if learning:
        st.info("Basis convention used here: Basis = Spot − Futures. The simulated paths are illustrative, not forecasts.")

with tabs[3]:
    st.subheader("Cash-and-Carry Arbitrage Lab")
    financing = spot*(np.exp(r*T)-1)
    income = spot*(1-np.exp(-q*T)) if q>0 else 0
    storage = spot*(np.exp(u*T)-1) if u>0 else 0
    arb_tc = st.number_input("Round-trip transaction + execution costs (₹ per unit)",0.0,value=20.0)
    upper = fair+arb_tc
    lower = fair-arb_tc
    if current_fut > upper:
        signal="Potential cash-and-carry"
        gross=current_fut-fair
        net_arb=gross-arb_tc
    elif current_fut < lower:
        signal="Potential reverse cash-and-carry"
        gross=fair-current_fut
        net_arb=gross-arb_tc
    else:
        signal="Inside no-arbitrage band"
        gross=abs(current_fut-fair)
        net_arb=0
    st.metric("Arbitrage Status",signal)
    st.metric("Estimated Net Arbitrage Profit per Unit",money(net_arb))
    flows=pd.DataFrame({
        "Component":["Spot purchase / sale reference","Financing cost","Estimated income benefit","Storage cost","Futures fair value","Market futures price","Transaction-cost band","Net estimated opportunity"],
        "Amount (₹)":[spot,financing,income,storage,fair,current_fut,arb_tc,net_arb]
    })
    st.dataframe(flows,use_container_width=True,hide_index=True)
    if learning:
        st.info("A theoretical price gap is not automatically tradable arbitrage. Financing, bid–ask spreads, taxes, short-borrow constraints, margin and execution risk matter.")

with tabs[4]:
    st.subheader("Daily Mark-to-Market Simulator")
    sim_days=st.slider("Simulation days",10,60,20)
    init_margin_pct=st.slider("Initial margin %",5.0,30.0,12.0,.5,key="im")
    maint_ratio=st.slider("Maintenance margin as % of initial margin",50.0,95.0,75.0,1.0)
    vol=st.slider("Daily futures volatility (%)",0.1,5.0,1.2,.1)
    seed=st.number_input("Simulation seed",1,999,42)
    rng=np.random.default_rng(seed)
    rets=rng.normal(0,vol/100,sim_days)
    prices=[current_fut]
    for rr in rets: prices.append(prices[-1]*(1+rr))
    initial_margin=current_fut*lot*contracts*init_margin_pct/100
    maintenance=initial_margin*maint_ratio/100
    bal=initial_margin
    rows=[]
    for i in range(1,len(prices)):
        daily=(prices[i]-prices[i-1])*lot*contracts*(1 if position=="Long" else -1)
        opening=bal
        bal+=daily
        call=bal<maintenance
        add=max(initial_margin-bal,0) if call else 0
        closing=bal
        if call: bal+=add
        rows.append([i,prices[i],daily,opening,closing,maintenance,"YES" if call else "No",add])
    mtm=pd.DataFrame(rows,columns=["Day","Settlement Price","Daily P&L","Opening Margin","Closing Margin","Maintenance Level","Margin Call","Additional Margin"])
    st.dataframe(mtm.style.format({c:"{:,.2f}" for c in mtm.columns if c not in ["Day","Margin Call"]}),use_container_width=True)
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=mtm.Day,y=mtm["Closing Margin"],name="Margin balance"))
    fig.add_trace(go.Scatter(x=mtm.Day,y=mtm["Maintenance Level"],name="Maintenance threshold"))
    fig.update_layout(title="Margin Account Simulation",xaxis_title="Day",yaxis_title="₹")
    st.plotly_chart(fig,use_container_width=True)

with tabs[5]:
    st.subheader("Hedging Simulator")
    hedge_type=st.radio("Hedge type",["Long Hedge","Short Hedge"],horizontal=True)
    exposure=st.number_input("Physical exposure quantity",min_value=1.0,value=1000.0)
    future_spot=st.slider("Future spot price",float(spot*.7),float(spot*1.3),float(spot),step=float(max(spot*.005,.01)))
    fut_settle=future_spot
    ncontracts=st.number_input("Hedge contracts",1,value=max(1,int(exposure/(lot))))
    fut_pl=pnl("Long" if hedge_type=="Long Hedge" else "Short",entry,fut_settle,lot,ncontracts)
    physical_cost=exposure*future_spot
    if hedge_type=="Long Hedge":
        effective=physical_cost-fut_pl
        st.metric("Unhedged purchase cost",money(physical_cost))
        st.metric("Futures hedge P&L",money(fut_pl))
        st.metric("Effective purchase cost",money(effective))
    else:
        sale=physical_cost
        effective=sale+fut_pl
        st.metric("Unhedged sale proceeds",money(sale))
        st.metric("Futures hedge P&L",money(fut_pl))
        st.metric("Effective sale proceeds",money(effective))
    st.subheader("Cross-Hedge Calculator")
    rho=st.slider("Correlation ρ",-1.0,1.0,.85,.01)
    sigma_s=st.number_input("Spot return volatility σS",.001,value=.20)
    sigma_f=st.number_input("Futures return volatility σF",.001,value=.18)
    h=rho*(sigma_s/sigma_f)
    contract_value=current_fut*lot
    N=h*(spot*exposure/contract_value)
    st.metric("Optimal Hedge Ratio h*",f"{h:.3f}")
    st.metric("Optimal Contracts N*",f"{N:.2f}")

with tabs[6]:
    st.subheader("Scenario Analysis")
    scenarios=pd.DataFrame({
        "Scenario":["Bearish","Base","Bullish"],
        "Settlement Price":[current_fut*.90,current_fut,current_fut*1.10]
    })
    scenarios["Long P&L"]=(scenarios["Settlement Price"]-entry)*lot*contracts
    scenarios["Short P&L"]=-scenarios["Long P&L"]
    scenarios["Basis at Expiry (assumed convergence)"]=0.0
    st.dataframe(scenarios.style.format({c:"{:,.2f}" for c in scenarios.columns if c!="Scenario"}),use_container_width=True)
    fig=go.Figure()
    fig.add_trace(go.Bar(x=scenarios.Scenario,y=scenarios["Long P&L"],name="Long P&L"))
    fig.add_trace(go.Bar(x=scenarios.Scenario,y=scenarios["Short P&L"],name="Short P&L"))
    fig.update_layout(title="Scenario P&L Comparison",barmode="group",yaxis_title="₹")
    st.plotly_chart(fig,use_container_width=True)

    st.subheader("Risk Monitor")
    margin_assumed=notional*.12
    buffer=margin_assumed-maintenance if "maintenance" in locals() else margin_assumed*.25
    c=st.columns(5)
    c[0].metric("Notional Exposure",money(notional))
    c[1].metric("P&L for 1% Move",money(notional*.01))
    c[2].metric("P&L for 5% Move",money(notional*.05))
    c[3].metric("Approx. Leverage",f"{notional/margin_assumed:.2f}×")
    c[4].metric("Margin Buffer",money(buffer))

with tabs[7]:
    st.subheader("Learning Mode Exercises")
    st.markdown("""
**1. Prediction exercise:** If you are long futures and the futures price falls 5%, what happens to P&L?

**2. Fair-value exercise:** Increase the risk-free rate in the sidebar. Observe the theoretical futures price.

**3. Convergence exercise:** Compare the simulated spot and futures paths near expiry.

**4. Arbitrage exercise:** Raise the market futures price above fair value plus transaction costs and observe the signal.

**5. Margin exercise:** Increase daily volatility and rerun the MTM simulation. Observe whether margin calls become more frequent.
""")
    with st.expander("Show conceptual answers"):
        st.write("""
1. A long futures position loses when the futures price falls below its entry price.
2. Holding other variables constant, a higher financing rate raises cost-of-carry fair value.
3. Spot and futures should converge near expiry because a persistent exploitable price gap cannot remain at settlement under ideal no-arbitrage conditions.
4. A sufficiently overpriced future can create a cash-and-carry setup, subject to real-world costs and constraints.
5. Larger adverse daily moves can deplete the margin account faster and trigger margin calls.
""")

st.divider()
st.caption("Educational Futures Market Simulator • All default values are simulated • Verify formulas and market conventions before academic or professional use.")
'''

req = """streamlit>=1.40,<2
pandas>=2.0,<3
numpy>=1.26,<3
plotly>=5.20,<7
"""

readme = """# Futures Trading Learning Lab

An educational Streamlit dashboard for futures derivatives.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
