import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Inflight Retail Performance", layout="wide", page_icon="✈️")

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .metric-highlight { background:#f0f7ff; border-left:4px solid #378ADD; padding:12px 16px; border-radius:6px; margin-bottom:8px; }
  .insight-box { background:#fffbea; border-left:4px solid #BA7517; padding:12px 16px; border-radius:6px; margin:8px 0; font-size:14px; }
  .good-box   { background:#edfaf3; border-left:4px solid #1D9E75; padding:12px 16px; border-radius:6px; margin:8px 0; font-size:14px; }
  .warn-box   { background:#fff4e5; border-left:4px solid #E24B4A; padding:12px 16px; border-radius:6px; margin:8px 0; font-size:14px; }
  h1 { font-size:26px !important; }
  h2 { font-size:20px !important; }
  h3 { font-size:16px !important; }
</style>
""", unsafe_allow_html=True)

# ── Load & preprocess ────────────────────────────────────────────────────────
@st.cache_data
def load_data(path):
    df = pd.read_csv(path)
    df['created_at_myt'] = pd.to_datetime(df['created_at_myt'])
    for col in ['unit_price','total_quantity','myr_total_amount','myr_paid_amount','myr_discount_amount']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['line_rev'] = df['unit_price'] * df['total_quantity']
    df['date'] = df['created_at_myt'].dt.date
    return df

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/AirAsia_New_Logo.svg/320px-AirAsia_New_Logo.svg.png", width=120)
    st.markdown("## ✈️ Inflight Retail")
    st.markdown("---")
    uploaded = st.file_uploader("Upload CSV data", type="csv")
    st.markdown("---")
    st.markdown("**L5 = Last 5 days**  \nPrior = everything before")
    st.markdown("---")
    st.markdown("**Filter by category**")

if uploaded:
    df = load_data(uploaded)
else:
    st.info("👈 Upload your performance CSV to get started.")
    st.stop()

# ── Date segmentation ────────────────────────────────────────────────────────
max_date = df['date'].max()
all_dates = sorted(df['date'].unique())

with st.sidebar:
    n_days = st.slider("'Recent' window (days)", min_value=3, max_value=14, value=5)
    cutoff = sorted(all_dates)[-n_days]
    st.caption(f"Recent: {cutoff} → {max_date}")
    st.markdown("---")
    cat_options = sorted(df['main_category'].dropna().unique())
    selected_cats = st.multiselect("Categories", cat_options, default=cat_options)

df = df[df['main_category'].isin(selected_cats)]
df['period'] = df['date'].apply(lambda d: f'Last {n_days} days' if d >= cutoff else 'Prior period')

prior_days = len([d for d in all_dates if d < cutoff])
recent_days = n_days

order_df = df.drop_duplicates(subset='order_number').copy()

RECENT = f'Last {n_days} days'
PRIOR  = 'Prior period'

def period_stats(odf, period):
    sub = odf[odf['period']==period]
    return {
        'orders': len(sub),
        'revenue': sub['myr_paid_amount'].sum(),
        'discount': sub['myr_discount_amount'].sum(),
        'aov': sub['myr_paid_amount'].mean(),
        'days': recent_days if period==RECENT else prior_days
    }

rec  = period_stats(order_df, RECENT)
pri  = period_stats(order_df, PRIOR)

def delta(a, b):
    if b == 0: return 0
    return (a - b) / b * 100

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE TABS
# ═══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🍾 Liquor", "🧴 Skincare", "💰 Discounts"])

# ══════════════════════════════
# TAB 1 — OVERVIEW
# ══════════════════════════════
with tab1:
    st.markdown("# Performance Overview")
    st.markdown(f"Comparing **last {n_days} days** vs prior period ({prior_days} days)")

    # KPI row
    c1,c2,c3,c4,c5 = st.columns(5)
    rec_daily = rec['revenue']/rec['days']
    pri_daily = pri['revenue']/pri['days']
    c1.metric("Paid Revenue (recent)", f"MYR {rec['revenue']:,.0f}", f"{delta(rec_daily,pri_daily):+.1f}% daily rate")
    c2.metric("Orders (recent)", f"{rec['orders']:,}", f"{delta(rec['orders']/rec['days'], pri['orders']/pri['days']):+.1f}% daily rate")
    c3.metric("Avg Order Value", f"MYR {rec['aov']:,.0f}", f"{delta(rec['aov'],pri['aov']):+.1f}% vs prior")
    c4.metric("Discount Given (recent)", f"MYR {rec['discount']:,.0f}")
    disc_pct_rec = rec['discount'] / (rec['revenue'] + rec['discount']) * 100 if rec['revenue'] else 0
    disc_pct_pri = pri['discount'] / (pri['revenue'] + pri['discount']) * 100 if pri['revenue'] else 0
    c5.metric("Discount % of Gross", f"{disc_pct_rec:.1f}%", f"{disc_pct_rec-disc_pct_pri:+.1f}pp vs prior")

    st.markdown("---")

    # Monthly revenue trend
    col_a, col_b = st.columns([2,1])
    with col_a:
        st.markdown("### Monthly revenue & orders")
        monthly = order_df.groupby(order_df['created_at_myt'].dt.to_period('M')).agg(
            revenue=('myr_paid_amount','sum'), orders=('order_number','count')
        ).reset_index()
        monthly['month'] = monthly['created_at_myt'].astype(str)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=monthly['month'], y=monthly['revenue'], name='Revenue', marker_color='#378ADD', opacity=0.85), secondary_y=False)
        fig.add_trace(go.Scatter(x=monthly['month'], y=monthly['orders'], name='Orders', line=dict(color='#1D9E75', width=2), mode='lines+markers'), secondary_y=True)
        fig.update_layout(height=300, margin=dict(t=10,b=10,l=10,r=10), legend=dict(orientation='h', y=1.1), plot_bgcolor='rgba(0,0,0,0)')
        fig.update_yaxes(title_text="MYR Revenue", secondary_y=False, tickprefix="MYR ")
        fig.update_yaxes(title_text="Orders", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("### Revenue by carrier")
        carrier = order_df.groupby('CarrierCode')['myr_paid_amount'].sum().sort_values(ascending=False).reset_index()
        fig2 = px.pie(carrier, names='CarrierCode', values='myr_paid_amount',
                      color_discrete_sequence=['#378ADD','#1D9E75','#BA7517','#888780'],
                      hole=0.55)
        fig2.update_layout(height=300, margin=dict(t=10,b=10,l=10,r=10), showlegend=True)
        fig2.update_traces(textinfo='label+percent')
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    col_c, col_d, col_e = st.columns(3)

    with col_c:
        st.markdown("### Top categories — recent period")
        cat_rev = df[df['period']==RECENT].groupby('main_category')['line_rev'].sum().sort_values(ascending=True).reset_index()
        fig3 = px.bar(cat_rev, x='line_rev', y='main_category', orientation='h',
                      color_discrete_sequence=['#534AB7'])
        fig3.update_layout(height=280, margin=dict(t=10,b=10,l=10,r=10), xaxis_title='Revenue (MYR)', yaxis_title='', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        st.markdown("### Int'l vs Domestic")
        fg = order_df.groupby('FlightGroup')['myr_paid_amount'].sum().reset_index()
        fig4 = px.pie(fg, names='FlightGroup', values='myr_paid_amount', hole=0.55,
                      color_discrete_sequence=['#378ADD','#B5D4F4'])
        fig4.update_layout(height=280, margin=dict(t=10,b=10,l=10,r=10))
        fig4.update_traces(textinfo='label+percent')
        st.plotly_chart(fig4, use_container_width=True)

    with col_e:
        st.markdown("### Payment method")
        pm = order_df.groupby('payment_method')['myr_paid_amount'].sum().dropna().reset_index()
        fig5 = px.pie(pm, names='payment_method', values='myr_paid_amount', hole=0.55,
                      color_discrete_sequence=['#1D9E75','#9FE1CB','#E1F5EE'])
        fig5.update_layout(height=280, margin=dict(t=10,b=10,l=10,r=10))
        fig5.update_traces(textinfo='label+percent')
        st.plotly_chart(fig5, use_container_width=True)

    st.markdown("---")
    st.markdown("### Daily revenue rate — recent vs prior (by category)")

    cat_comp = []
    for cat in df['main_category'].dropna().unique():
        sub = df[df['main_category']==cat]
        r_rev = sub[sub['period']==RECENT]['line_rev'].sum() / recent_days
        p_rev = sub[sub['period']==PRIOR]['line_rev'].sum() / prior_days
        cat_comp.append({'Category': cat, 'Last 5 days (daily)': r_rev, 'Prior period (daily)': p_rev})
    cat_comp_df = pd.DataFrame(cat_comp).sort_values('Last 5 days (daily)', ascending=False)

    fig6 = go.Figure()
    fig6.add_trace(go.Bar(name=f'Last {n_days} days', x=cat_comp_df['Category'], y=cat_comp_df['Last 5 days (daily)'], marker_color='#378ADD', opacity=0.9))
    fig6.add_trace(go.Bar(name='Prior period', x=cat_comp_df['Category'], y=cat_comp_df['Prior period (daily)'], marker_color='#B5D4F4', opacity=0.9))
    fig6.update_layout(barmode='group', height=300, margin=dict(t=10,b=10,l=10,r=10),
                       yaxis_title='MYR / day', plot_bgcolor='rgba(0,0,0,0)',
                       legend=dict(orientation='h', y=1.1))
    st.plotly_chart(fig6, use_container_width=True)

    st.markdown("### Top revenue items — recent period")
    item_rev = df[df['period']==RECENT].groupby(['item_name','main_category','item_brand']).agg(
        qty=('total_quantity','sum'), revenue=('line_rev','sum'), orders=('order_number','nunique')
    ).reset_index().sort_values('revenue', ascending=False).head(20)
    item_rev['revenue'] = item_rev['revenue'].round(0)
    item_rev['avg_price'] = (item_rev['revenue']/item_rev['qty']).round(1)
    st.dataframe(item_rev.rename(columns={'item_name':'Item','main_category':'Category','item_brand':'Brand',
                                           'qty':'Qty Sold','revenue':'Revenue (MYR)','orders':'Orders','avg_price':'Avg Unit Price'}),
                 use_container_width=True, hide_index=True)

    st.markdown("""
    <div class='insight-box'>💡 <b>Key insight:</b> Fragrance, Skincare and Liquor are all running above their prior daily rates.
    Skincare shows the sharpest uplift (+70% daily rate), driven by Laneige duo bundles and Sulwhasoo premium serums.</div>
    """, unsafe_allow_html=True)


# ══════════════════════════════
# TAB 2 — LIQUOR
# ══════════════════════════════
with tab2:
    st.markdown("# 🍾 Liquor Deep Dive")

    liq = df[df['main_category']=='Liquor']
    liq_ord = order_df[order_df['main_category']=='Liquor']

    liq_rec = liq[liq['period']==RECENT]
    liq_pri = liq[liq['period']==PRIOR]

    rec_daily_liq = liq_rec['line_rev'].sum() / recent_days
    pri_daily_liq = liq_pri['line_rev'].sum() / prior_days

    c1,c2,c3,c4 = st.columns(4)
    c1.metric(f"Revenue (last {n_days}d)", f"MYR {liq_rec['line_rev'].sum():,.0f}")
    c2.metric("Daily avg (recent)", f"MYR {rec_daily_liq:,.0f}", f"{delta(rec_daily_liq, pri_daily_liq):+.1f}% vs prior")
    c3.metric("Units sold (recent)", f"{liq_rec['total_quantity'].sum():.0f}", f"vs {liq_pri['total_quantity'].sum()/prior_days*recent_days:.0f} expected at prior rate")
    c4.metric("Active brands (recent)", f"{liq_rec['item_brand'].nunique()}")

    st.markdown("---")

    # SKU comparison
    last5_items = liq_rec.groupby('item_name').agg(qty_l5=('total_quantity','sum'), rev_l5=('line_rev','sum'), brand=('item_brand','first'), price=('unit_price','first')).reset_index()
    prior_items = liq_pri.groupby('item_name').agg(qty_pr=('total_quantity','sum'), rev_pr=('line_rev','sum')).reset_index()
    merged = last5_items.merge(prior_items, on='item_name', how='left').fillna(0)
    merged['daily_l5'] = merged['qty_l5'] / recent_days
    merged['daily_pr'] = merged['qty_pr'] / prior_days
    merged['uplift'] = (merged['daily_l5'] - merged['daily_pr']).round(2)
    top_skus = merged.sort_values('rev_l5', ascending=False).head(15)

    col_a, col_b = st.columns([3,2])
    with col_a:
        st.markdown("### Top SKUs by revenue — recent period")
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        colors = ['#1D9E75' if u >= 3 else '#378ADD' if u >= 0 else '#E24B4A' for u in top_skus['uplift']]
        fig.add_trace(go.Bar(x=top_skus['rev_l5'], y=top_skus['item_name'], orientation='h',
                             name='Revenue', marker_color='#BA7517', opacity=0.85), secondary_y=False)
        fig.add_trace(go.Scatter(x=top_skus['uplift'], y=top_skus['item_name'], mode='markers',
                                 marker=dict(color=colors, size=10, symbol='circle'),
                                 name='Daily uplift (units)'), secondary_y=True)
        fig.update_layout(height=420, margin=dict(t=10,b=10,l=10,r=20), plot_bgcolor='rgba(0,0,0,0)',
                          legend=dict(orientation='h', y=1.05))
        fig.update_xaxes(title_text="Revenue (MYR)", secondary_y=False)
        fig.update_yaxes(autorange='reversed')
        st.plotly_chart(fig, use_container_width=True)
        st.caption("🟢 dot = strong uplift (≥3 units/day) · 🔵 moderate · 🔴 declining")

    with col_b:
        st.markdown("### Brand revenue — recent period")
        brand_rev = liq_rec.groupby('item_brand').agg(rev=('line_rev','sum'), qty=('total_quantity','sum')).reset_index().sort_values('rev', ascending=True).tail(10)
        fig2 = px.bar(brand_rev, x='rev', y='item_brand', orientation='h',
                      color_discrete_sequence=['#BA7517'])
        fig2.update_layout(height=420, margin=dict(t=10,b=10,l=10,r=10), xaxis_title='Revenue (MYR)', yaxis_title='', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.markdown("### SKU-level comparison table")
    display = merged.sort_values('rev_l5', ascending=False).head(20).copy()
    display['rev_l5'] = display['rev_l5'].round(0)
    display['uplift_label'] = display['uplift'].apply(lambda x: f"{'↑' if x>0 else '↓'} {abs(x):.2f}/day")
    st.dataframe(display[['item_name','brand','price','qty_l5','rev_l5','daily_l5','daily_pr','uplift_label']].rename(columns={
        'item_name':'Item','brand':'Brand','price':'Unit Price','qty_l5':'Qty (recent)',
        'rev_l5':'Revenue (MYR)','daily_l5':'Daily qty (recent)','daily_pr':'Daily qty (prior)','uplift_label':'Uplift'
    }), use_container_width=True, hide_index=True)

    st.markdown("""
    <div class='good-box'>✅ <b>Scotch whisky is the anchor.</b> Glenlivet and Chivas together account for ~25% of liquor revenue. Premium aged expressions are near-zero in the prior period — likely new listings or seasonal push.</div>
    <div class='insight-box'>💡 <b>Captain Morgan surprise.</b> Lowest-priced top SKU (MYR 78) but highest volume uplift (+8 units/day). Likely promo or placement driven — monitor margin impact.</div>
    <div class='warn-box'>⚠️ <b>Suntory divergence.</b> Roku Gin and Toki Whisky both declining vs prior despite Suntory ranking 4th by brand revenue. Other SKUs masking the slowdown.</div>
    """, unsafe_allow_html=True)


# ══════════════════════════════
# TAB 3 — SKINCARE
# ══════════════════════════════
with tab3:
    st.markdown("# 🧴 Skincare Deep Dive")

    skin = df[df['main_category']=='Skincare']
    skin_rec = skin[skin['period']==RECENT]
    skin_pri = skin[skin['period']==PRIOR]

    rec_daily_sk = skin_rec['line_rev'].sum() / recent_days
    pri_daily_sk = skin_pri['line_rev'].sum() / prior_days

    c1,c2,c3,c4 = st.columns(4)
    c1.metric(f"Revenue (last {n_days}d)", f"MYR {skin_rec['line_rev'].sum():,.0f}")
    c2.metric("Daily avg (recent)", f"MYR {rec_daily_sk:,.0f}", f"{delta(rec_daily_sk,pri_daily_sk):+.1f}% vs prior — sharpest lift")
    c3.metric("Units sold (recent)", f"{skin_rec['total_quantity'].sum():.0f}")
    c4.metric("Brands active (recent)", f"{skin_rec['item_brand'].nunique()}")

    st.markdown("---")

    last5_sk = skin_rec.groupby('item_name').agg(qty_l5=('total_quantity','sum'), rev_l5=('line_rev','sum'), brand=('item_brand','first'), price=('unit_price','first')).reset_index()
    prior_sk = skin_pri.groupby('item_name').agg(qty_pr=('total_quantity','sum'), rev_pr=('line_rev','sum')).reset_index()
    merged_sk = last5_sk.merge(prior_sk, on='item_name', how='left').fillna(0)
    merged_sk['daily_l5'] = merged_sk['qty_l5'] / recent_days
    merged_sk['daily_pr'] = merged_sk['qty_pr'] / prior_days
    merged_sk['uplift'] = (merged_sk['daily_l5'] - merged_sk['daily_pr']).round(2)
    merged_sk['is_new'] = merged_sk['qty_pr'] == 0
    top_sk = merged_sk.sort_values('rev_l5', ascending=False).head(15)

    col_a, col_b = st.columns([3,2])
    with col_a:
        st.markdown("### Top SKUs — recent period")
        up_colors = ['#1D9E75' if u >= 3 else '#378ADD' if u >= 0 else '#E24B4A' for u in top_sk['uplift']]
        labels = top_sk['item_name'].apply(lambda x: x[:45] + (' ★NEW' if merged_sk.loc[merged_sk['item_name']==x,'is_new'].values[0] else ''))
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=top_sk['rev_l5'], y=labels, orientation='h',
                             name='Revenue', marker_color='#1D9E75', opacity=0.85), secondary_y=False)
        fig.add_trace(go.Scatter(x=top_sk['uplift'], y=labels, mode='markers',
                                 marker=dict(color=up_colors, size=10),
                                 name='Daily uplift (units)'), secondary_y=True)
        fig.update_layout(height=420, margin=dict(t=10,b=10,l=10,r=20), plot_bgcolor='rgba(0,0,0,0)',
                          legend=dict(orientation='h', y=1.05))
        fig.update_yaxes(autorange='reversed')
        fig.update_xaxes(title_text="Revenue (MYR)")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("★NEW = zero sales in prior period · 🟢 strong uplift · 🔴 declining")

    with col_b:
        st.markdown("### Brand revenue — recent period")
        brand_sk = skin_rec.groupby('item_brand').agg(rev=('line_rev','sum'), qty=('total_quantity','sum')).reset_index().sort_values('rev', ascending=True).tail(10)
        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(go.Bar(x=brand_sk['rev'], y=brand_sk['item_brand'], orientation='h',
                              marker_color='#1D9E75', opacity=0.85, name='Revenue'), secondary_y=False)
        fig2.add_trace(go.Scatter(x=brand_sk['qty'], y=brand_sk['item_brand'], mode='markers',
                                  marker=dict(color='#9FE1CB', size=9), name='Qty'), secondary_y=True)
        fig2.update_layout(height=420, margin=dict(t=10,b=10,l=10,r=10), plot_bgcolor='rgba(0,0,0,0)',
                           legend=dict(orientation='h', y=1.05))
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.markdown("### SKU detail table")
    disp_sk = merged_sk.sort_values('rev_l5', ascending=False).head(20).copy()
    disp_sk['rev_l5'] = disp_sk['rev_l5'].round(0)
    disp_sk['new'] = disp_sk['is_new'].apply(lambda x: '★ NEW' if x else '')
    disp_sk['uplift_label'] = disp_sk['uplift'].apply(lambda x: f"{'↑' if x>0 else '↓'} {abs(x):.2f}/day")
    st.dataframe(disp_sk[['item_name','brand','price','new','qty_l5','rev_l5','daily_l5','daily_pr','uplift_label']].rename(columns={
        'item_name':'Item','brand':'Brand','price':'Unit Price','new':'New?',
        'qty_l5':'Qty (recent)','rev_l5':'Revenue (MYR)','daily_l5':'Daily qty (recent)',
        'daily_pr':'Daily qty (prior)','uplift_label':'Uplift'
    }), use_container_width=True, hide_index=True)

    st.markdown("""
    <div class='good-box'>✅ <b>Laneige duo bundles are the category engine.</b> Water Sleeping Mask Duo alone is 12% of skincare revenue. Bundle format at accessible price (MYR 177) is driving high volume uplift (+7.3 units/day).</div>
    <div class='good-box'>✅ <b>Sulwhasoo punches on value.</b> 31 units, MYR 10.5K — First Care Serum at MYR 650 is nearly all incremental. Ultra-premium, near-zero prior run rate.</div>
    <div class='insight-box'>💡 <b>Emerging affordable SKUs to watch:</b> Elensilia Ampoule, Mediheal Mask 10-pack, L.SOULLE Sunscreen — all sub-MYR 100 with strong volume uplift (3–4 units/day). High repurchase potential.</div>
    """, unsafe_allow_html=True)


# ══════════════════════════════
# TAB 4 — DISCOUNTS
# ══════════════════════════════
with tab4:
    st.markdown("# 💰 Discount Analysis")
    st.markdown("Order-level analysis — discount amount, AOV, and code effectiveness")

    # category selector
    disc_cats = st.multiselect("Filter category", cat_options, default=['Liquor','Skincare','Fragrance'], key='disc_cat')
    disc_df = order_df[order_df['main_category'].isin(disc_cats)].copy() if disc_cats else order_df.copy()

    rec_disc = disc_df[disc_df['period']==RECENT]
    pri_disc = disc_df[disc_df['period']==PRIOR]

    def disc_rate(sub):
        total = len(sub)
        if total == 0: return 0
        return len(sub[sub['DiscountGroup']!='Full_Price']) / total * 100

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Discount rate (recent)", f"{disc_rate(rec_disc):.1f}%", f"{disc_rate(rec_disc)-disc_rate(pri_disc):+.1f}pp vs prior")
    disc_aov_rec = rec_disc[rec_disc['DiscountGroup']!='Full_Price']['myr_paid_amount'].mean()
    disc_aov_pri = pri_disc[pri_disc['DiscountGroup']!='Full_Price']['myr_paid_amount'].mean()
    c2.metric("Discounted AOV (recent)", f"MYR {disc_aov_rec:,.0f}", f"{delta(disc_aov_rec, disc_aov_pri):+.1f}% vs prior")
    fp_aov_rec = rec_disc[rec_disc['DiscountGroup']=='Full_Price']['myr_paid_amount'].mean()
    fp_aov_pri = pri_disc[pri_disc['DiscountGroup']=='Full_Price']['myr_paid_amount'].mean()
    c3.metric("Full-price AOV (recent)", f"MYR {fp_aov_rec:,.0f}", f"{delta(fp_aov_rec, fp_aov_pri):+.1f}% vs prior")
    avg_disc_rec = rec_disc[rec_disc['myr_discount_amount'].notna()]['myr_discount_amount'].mean()
    c4.metric("Avg discount per order", f"MYR {avg_disc_rec:,.0f}")

    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### Discount code breakdown — recent period")
        code_summary = rec_disc.groupby('DiscountGroup').agg(
            orders=('order_number','count'),
            avg_disc=('myr_discount_amount','mean'),
            total_disc=('myr_discount_amount','sum')
        ).reset_index().sort_values('orders', ascending=False)
        code_summary['avg_disc'] = code_summary['avg_disc'].fillna(0).round(0)
        code_summary['total_disc'] = code_summary['total_disc'].fillna(0).round(0)

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=code_summary['DiscountGroup'], y=code_summary['orders'],
                             name='Orders', marker_color='#BA7517', opacity=0.85), secondary_y=False)
        fig.add_trace(go.Scatter(x=code_summary['DiscountGroup'], y=code_summary['avg_disc'],
                                 mode='lines+markers', marker=dict(color='#FAC775', size=8),
                                 line=dict(width=2), name='Avg discount (MYR)'), secondary_y=True)
        fig.update_layout(height=320, margin=dict(t=10,b=10,l=10,r=10), plot_bgcolor='rgba(0,0,0,0)',
                          legend=dict(orientation='h', y=1.1))
        fig.update_yaxes(title_text="Orders", secondary_y=False)
        fig.update_yaxes(title_text="Avg Discount (MYR)", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("### AOV: discounted vs full price by period")
        aov_data = pd.DataFrame({
            'Period': [f'Last {n_days} days', f'Last {n_days} days', 'Prior period', 'Prior period'],
            'Type': ['Discounted', 'Full Price', 'Discounted', 'Full Price'],
            'AOV': [disc_aov_rec, fp_aov_rec, disc_aov_pri, fp_aov_pri]
        })
        fig2 = px.bar(aov_data, x='Period', y='AOV', color='Type', barmode='group',
                      color_discrete_map={'Discounted': '#BA7517', 'Full Price': '#D3D1C7'})
        fig2.update_layout(height=320, margin=dict(t=10,b=10,l=10,r=10), plot_bgcolor='rgba(0,0,0,0)',
                           yaxis_title='AOV (MYR)', legend=dict(orientation='h', y=1.1))
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    col_c, col_d = st.columns(2)
    with col_c:
        st.markdown("### Revenue share: discounted vs full price")
        for period_label, sub in [(f'Last {n_days} days', rec_disc), ('Prior period', pri_disc)]:
            disc_rev = sub[sub['DiscountGroup']!='Full_Price']['myr_paid_amount'].sum()
            fp_rev   = sub[sub['DiscountGroup']=='Full_Price']['myr_paid_amount'].sum()
            total_r  = disc_rev + fp_rev
            if total_r > 0:
                st.markdown(f"**{period_label}**")
                st.progress(int(disc_rev/total_r*100), text=f"Discounted: MYR {disc_rev:,.0f} ({disc_rev/total_r*100:.0f}%) | Full price: MYR {fp_rev:,.0f} ({fp_rev/total_r*100:.0f}%)")

        st.markdown("")
        st.markdown("### Discount code table — recent")
        st.dataframe(code_summary.rename(columns={'DiscountGroup':'Code','orders':'Orders',
                                                   'avg_disc':'Avg Discount (MYR)','total_disc':'Total Discount (MYR)'}),
                     use_container_width=True, hide_index=True)

    with col_d:
        st.markdown("### Top items bought under top discount codes")
        top_codes = code_summary[code_summary['DiscountGroup']!='Full_Price']['DiscountGroup'].head(3).tolist()
        selected_code = st.selectbox("Select discount code", top_codes)
        code_orders = rec_disc[rec_disc['DiscountGroup']==selected_code]['order_number'].tolist()
        code_items = df[(df['order_number'].isin(code_orders)) & (df['main_category'].isin(disc_cats))].groupby('item_name').agg(
            qty=('total_quantity','sum'), orders=('order_number','nunique')
        ).reset_index().sort_values('qty', ascending=True).tail(12)
        fig3 = px.bar(code_items, x='qty', y='item_name', orientation='h',
                      color_discrete_sequence=['#534AB7'])
        fig3.update_layout(height=350, margin=dict(t=10,b=10,l=10,r=10),
                           xaxis_title='Qty sold', yaxis_title='', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown("""
    <div class='insight-box'>💡 <b>Discounts are driving up spend, not just conversions.</b> Discounted AOV in the recent period jumped to MYR 262 vs MYR 218 prior — buyers are using discounts to trade up to premium SKUs.</div>
    <div class='warn-box'>⚠️ <b>RAYA code: high risk, high ticket.</b> MYR 700 avg discount per order — buyers are purchasing Blue Label, XO Cognac. Net margin needs scrutiny. Validate if these are truly incremental purchases.</div>
    <div class='good-box'>✅ <b>EXTRA30 is the volume engine.</b> 42 orders, buyers going straight for Glenlivet, Jack Daniels, Chivas. 30% appears to be the conversion threshold for premium consideration.</div>
    """, unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(f"Data up to {max_date} · Last {n_days}-day window: {cutoff} → {max_date} · Prior: {prior_days} days")
