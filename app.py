import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- DATABASE CONNECTION ---
# Replace these with your actual Supabase credentials found in Project Settings > API
SUPABASE_URL = "https://dwjydbnrfkxcbgnwcxvp.supabase.co"
SUPABASE_KEY = "sb_publishable_JZjgavEYkgu5VAsvng8DKA_PMnGtI71"
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]

supabase = create_client(url, key)
@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Community Welfare Portal", page_icon="🏦", layout="wide")
st.title("🏦 Community Welfare & Subscription Portal")

# Sidebar navigation
menu = ["📊 Admin Dashboard", "📝 Member Registration", "🖤 File a Claim", "👥 View Member Directory"]
choice = st.sidebar.selectbox("Navigation Menu", menu)

# --- HELPER FUNCTIONS FOR FINANCIALS ---
def get_financial_summary():
    # Fetch all subscriptions (Income)
    subs = supabase.table("subscriptions").select("amount_paid, account_destination").execute().data
    # Fetch all claims (Expenses)
    claims = supabase.table("claims").select("amount_disbursed, account_source").execute().data
    
    df_subs = pd.DataFrame(subs)
    df_claims = pd.DataFrame(claims)
    
    cash_in_hand = 0
    cash_in_bank = 0
    
    if not df_subs.empty:
        cash_in_hand += df_subs[df_subs['account_destination'] == 'Cash in Hand']['amount_paid'].sum()
        cash_in_bank += df_subs[df_subs['account_destination'] == 'Cash in Bank']['amount_paid'].sum()
        
    if not df_claims.empty:
        cash_in_hand -= df_claims[df_claims['account_source'] == 'Cash in Hand']['amount_disbursed'].sum()
        cash_in_bank -= df_claims[df_claims['account_source'] == 'Cash in Bank']['amount_disbursed'].sum()
        
    return cash_in_hand, cash_in_bank, len(df_subs), len(df_claims)

# --- 1. ADMIN DASHBOARD ---
if choice == "📊 Admin Dashboard":
    st.header("Financial & Collection Overview")
    
    cash_hand, cash_bank, total_paid_counts, total_claims_counts = get_financial_summary()
    total_treasury = cash_hand + cash_bank
    
    # KPI Grid
    col1, col2, col3 = st.columns(3)
    col1.metric("💵 Cash in Hand", f"₹{cash_hand:,.2f}")
    col2.metric("🏦 Cash in Bank", f"₹{cash_bank:,.2f}")
    col3.metric("💰 Total Treasury Balance", f"₹{total_treasury:,.2f}")
    
    st.markdown("---")
    st.subheader("📋 Collection Reports & Insights")
    
    tab1, tab2 = st.tabs(["Payment Status by Year", "Recent Claims Log"])
    
    with tab1:
        search_year = st.number_input("Filter Status by Year", min_value=2020, max_value=2030, value=2026)
        
        # Get all members
        all_members = supabase.table("members").select("family_id, head_name, locality, phone_number").execute().data
        # Get payments for this year
        paid_this_year = supabase.table("subscriptions").select("family_id").eq("year", search_year).execute().data
        paid_ids = [p['family_id'] for p in paid_this_year]
        
        report_data = []
        for m in all_members:
            status = "✅ Paid" if m['family_id'] in paid_ids else "❌ Unpaid"
            report_data.append({
                "Head Name": m['head_name'],
                "Phone": m['phone_number'],
                "Locality": m['locality'],
                "Status": status
            })
            
        df_report = pd.DataFrame(report_data)
        if not df_report.empty:
            st.dataframe(df_report, use_container_width=True)
            
            # Summary Metrics
            paid_count = len(df_report[df_report['Status'] == "✅ Paid"])
            unpaid_count = len(df_report[df_report['Status'] == "❌ Unpaid"])
            st.write(f"**Summary for {search_year}:** {paid_count} Families Paid | {unpaid_count} Families Remaining.")
        else:
            st.info("No members registered yet.")

    with tab2:
        claims_data = supabase.table("claims").select("deceased_name, relationship, amount_disbursed, date_disbursed").execute().data
        if claims_data:
            st.dataframe(pd.DataFrame(claims_data), use_container_width=True)
        else:
            st.info("No welfare benefit claims recorded yet.")

# --- 2. MEMBER REGISTRATION FORM ---
elif choice == "📝 Member Registration":
    st.header("Register New Subscriber Family")
    
    with st.form("registration_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            head_name = st.text_input("Full Name (Head of Family)*")
            phone_number = st.text_input("Phone Number*")
            email_id = st.text_input("Email ID (Optional)")
            aadhaar_input = st.text_input("Aadhaar Number (12-Digit)", type="password")
        with col2:
            locality = st.selectbox("Locality / Ward", ["North Street", "South Street", "East Street", "West Street", "Colony Area"])
            village = st.text_input("Village", value="Local Village")
            local_address = st.text_area("Full Local Address")
            
        st.markdown("### Family Core Structure")
        spouse_name = st.text_input("Spouse Name")
        children_names = st.text_area("Children Names (Separated by commas)")
        parents_names = st.text_area("Parents' Names (Crucial for verifying future parent claims)")
        
        st.markdown("### Initial Subscription Payment")
        sub_year = st.number_input("Subscription Year", min_value=2020, max_value=2030, value=2026)
        payment_mode = st.radio("Payment Method", ["Cash", "Bank Transfer"])
        destination = st.radio("Route Funds To", ["Cash in Hand", "Cash in Bank"])
        
        submitted = st.form_submit_submit = st.form_submit_button("Submit & Save Record")
        
        if submitted:
            if not head_name or not phone_number:
                st.error("Head Name and Phone Number are required fields!")
            else:
                try:
                    # 1. Insert Member Record
                    member_data = {
                        "head_name": head_name, "phone_number": phone_number, "email_id": email_id,
                        "aadhaar_encrypted": "[Aadhaar Redacted]" if aadhaar_input else None,
                        "spouse_name": spouse_name, "children_names": children_names, "parents_names": parents_names,
                        "locality": locality, "village": village, "local_address": local_address
                    }
                    res = supabase.table("members").insert(member_data).execute()
                    new_family_id = res.data[0]['family_id']
                    
                    # 2. Insert Subscription Record
                    sub_data = {
                        "family_id": new_family_id, "year": sub_year, "amount_paid": 1000,
                        "payment_mode": payment_mode, "account_destination": destination
                    }
                    supabase.table("subscriptions").insert(sub_data).execute()
                    
                    st.success(f"🎉 Successfully registered {head_name}! Initial subscription of ₹1,000 recorded to {destination}.")
                except Exception as e:
                    st.error(f"Error saving data: {str(e)}")

# --- 3. FILE A DEATH BENEFIT CLAIM ---
elif choice == "🖤 File a Claim":
    st.header("Record Community Death Benefit Claim")
    
    # Load members list for search
    members_list = supabase.table("members").select("family_id, head_name, phone_number, spouse_name, parents_names").execute().data
    
    if not members_list:
        st.warning("Please add members to the system before filing a claim.")
    else:
        member_options = {f"{m['head_name']} ({m['phone_number']})": m for m in members_list}
        selected_key = st.selectbox("Search / Select Affected Family", list(member_options.keys()))
        selected_member = member_options[selected_key]
        
        # Display profile info for quick admin verification
        st.info(f"**Verification Check:** \n* **Spouse Listed:** {selected_member['spouse_name']} \n* **Parents Listed:** {selected_member['parents_names']}")
        
        with st.form("claim_form", clear_on_submit=True):
            deceased_name = st.text_input("Name of Deceased Person")
            relationship = st.radio("Relationship to Head of Family", ["Self", "Spouse", "Parent"])
            
            # Automated benefit payout calculations
            amount = 10000 if relationship in ["Self", "Spouse"] else 5000
            st.markdown(f"### **Calculated Benefit Payout:** `₹{amount:,}`")
            
            pay_mode = st.radio("Disbursement Method", ["Cash", "Bank Transfer"])
            source = st.radio("Deduct Funds From", ["Cash in Hand", "Cash in Bank"])
            
            claim_submitted = st.form_submit_button("Disburse & Finalize Claim")
            
            if claim_submitted:
                if not deceased_name:
                    st.error("Please provide the name of the deceased individual.")
                else:
                    claim_data = {
                        "family_id": selected_member['family_id'],
                        "deceased_name": deceased_name,
                        "relationship": relationship,
                        "amount_disbursed": amount,
                        "payment_mode": pay_mode,
                        "account_source": source
                    }
                    supabase.table("claims").insert(claim_data).execute()
                    st.success(f"📉 Claim recorded. ₹{amount:,} deducted from {source} for {deceased_name}'s funeral benefit support.")

# --- 4. VIEW MEMBER DIRECTORY ---
elif choice == "👥 View Member Directory":
    st.header("All Registered Families")
    members_raw = supabase.table("members").select("family_id, head_name, phone_number, locality, village, spouse_name, children_names, parents_names").execute().data
    if members_raw:
        st.dataframe(pd.DataFrame(members_raw), use_container_width=True)
    else:
        st.info("No members found in the database directory.")
