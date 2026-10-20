import json
from pathlib import Path
S=475.29953984
D=[1.3,1.35,1.4,1.45,1.5]

def pv(cf,r):
    return sum(x/(1+r)**(i+1) for i,x in enumerate(cf))

def operating_value(f,r,decline,plateau,buffer=500):
    # Cash after all normal exploration, development, production capital and
    # new-project decommissioning. Declining tail is a finite PV, not a growth
    # perpetuity. Buffer releases proportionally as operating scale declines.
    flat=pv([f]*plateau,r)
    tail=(f*(1-decline)+buffer*decline)/(r+decline)/(1+r)**plateau
    return flat+tail

def case(cfo,capex,new_aro,r,decline,bridge,equity,plateau=10,
         failure=0,financial_income_removed=50):
    f=cfo-financial_income_removed-capex-new_aro-failure
    current=operating_value(f,r,decline,plateau)
    remaining=operating_value(f,r,decline,plateau-5)
    bank=bridge-equity
    records=[]
    for year,d in enumerate(D,1):
        interest=.02*bank
        payout=d*S
        ending=bank+interest+f-payout
        assert abs(ending-(bank+interest+f-payout))<1e-9
        records.append(dict(year=year,opening=bank,interest=interest,
                            operating_cash=f,payout=payout,ending=ending))
        bank=ending
    terminal=(remaining+bank+equity)/S
    value=pv(D,r)+terminal/(1+r)**5
    return dict(fcf=f,rate=r,decline=decline,plateau=plateau,
                operating_value_0=current,operating_value_5=remaining,
                bridge_0=bridge,equity_associates=equity,cash_records=records,
                financial_5=bank+equity,terminal_per_share=terminal,
                value_per_share=value,asset_method=(current+bridge)/S,
                terminal_pv_share=terminal/(1+r)**5/value)

def main():
    lowargs=dict(cfo=2100,capex=1200,new_aro=30,r=.10,decline=.12,
                 bridge=2483.25-1191.06,equity=250)
    highargs=dict(cfo=2250,capex=1150,new_aro=40,r=.09,decline=.08,
                  bridge=2693.25-1191.06,equity=310)
    low=case(**lowargs);high=case(**highargs)
    sensitivity={}
    for tag,changes in [('plateau_8',{'plateau':8}),('plateau_12',{'plateau':12}),
                        ('failure_100',{'failure':100}),('capex_plus_100',{'capex':1300}),
                        ('cash_inflow_minus_200',{'cfo':1900}),('discount_11pct',{'r':.11}),
                        ('decline_15pct',{'decline':.15})]:
        sensitivity[tag]=case(**(lowargs|changes))['value_per_share']
    sensitivity['high_plateau_8']=case(**(highargs|{'plateau':8}))['value_per_share']
    sensitivity['high_plateau_12']=case(**(highargs|{'plateau':12}))['value_per_share']
    # Independent geometric sums, payment/retention and failure direction.
    explicit=sum(820*((1-.12)**max(t-10,0))/(1.1**t) for t in range(1,500))
    release=sum(500*.12*((1-.12)**(t-11))/(1.1**t) for t in range(11,500))
    assert abs(explicit+release-low['operating_value_0'])<1e-7
    assert sensitivity['failure_100']<low['value_per_share']
    assert sensitivity['capex_plus_100']<low['value_per_share']
    assert sensitivity['plateau_8']<low['value_per_share']<sensitivity['plateau_12']
    assert abs(pv([100],.1)-100/1.1)<1e-12
    assert abs(pv([100,100],0)-200)<1e-12
    assert abs(sum(500*.12*.88**i for i in range(500))-500)<1e-7
    assert len(low['cash_records'])==len(D)==5
    result=dict(shares=S,low=low,high=high,sensitivities=sensitivity,
       value_range={'low':round(low['value_per_share'],2),'high':round(high['value_per_share'],2),'currency':'CNY'},
       return_model={'schema_version':1,'method':'annual_common_equity_irr_v1','currency':'CNY',
         'model_as_of':'2026-09-06T19:10:51+08:00','base_case_distributions_per_share':D,
         'base_case_terminal_equity_value_range_per_share':{'year_5':{
           'low':round(low['terminal_per_share'],2),'high':round(high['terminal_per_share'],2)}}},
       physical_check={'remaining_proved_including_associates_boe_100m':77.731-5.4,
         'lifetime_production_low':7.8*(10+.88/.12),
         'lifetime_production_high':8*(10+.92/.08),
         'additional_resources_required_low':7.8*(10+.88/.12)-(77.731-5.4),
         'additional_resources_required_high':8*(10+.92/.08)-(77.731-5.4)},
       finite_proved_nav={'low':(6538.23+2483.25)/S,'high':(8088.23+2693.25)/S},
       tests='passed')
    Path(__file__).with_name('2026-H1-output.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
