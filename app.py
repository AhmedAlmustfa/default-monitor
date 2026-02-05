import streamlit as st
import pandas as pd
import joblib
from sqlalchemy import create_engine
import datetime

# --- CONFIGURATION ---
# Replace this with your actual Neon connection string!
DB_URL = "postgresql://neondb_owner:npg_B4cSC0gWZMhn@ep-dark-field-agchgfsk-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
engine = create_engine(DB_URL)

# Load the model you downloaded from Colab
@st.cache_resource
def load_model():
    return joblib.load("credit_model.joblib")

model = load_model()

# --- APP LAYOUT ---
st.set_page_config(page_title="Bank Risk Portal", layout="wide")

st.title("🏦 Banking Default & Business Monitor")

# Sidebar for Navigation
page = st.sidebar.selectbox("Go to", ["New Loan Application", "Business Dashboard"])

if page == "New Loan Application":
    st.header("Assess New Customer")
    
    col1, col2 = st.columns(2)
    with col1:
        duration = st.number_input("Loan Duration (Months)", value=12)
        amount = st.number_input("Loan Amount ($)", value=1000)
    with col2:
        rate = st.slider("Installment Rate (% of Income)", 1, 10, 4)
        age = st.number_input("Customer Age", min_value=18, value=30)

    if st.button("Run Risk Assessment"):
        # 1. Prediction Logic
        # Columns must match the names used in training: 
        # ['months_loan_duration', 'amount', 'installment_rate', 'age_years']
        input_data = pd.DataFrame([[duration, amount, rate, age]], 
                                   columns=['months_loan_duration', 'amount', 'installment_rate', 'age'])
        
        prediction = model.predict(input_data)[0]
        # Dataset note: 1=Default, 2=No Default (adjusting to common sense 0/1)
        result_text = "⚠️ HIGH RISK (Potential Default)" if prediction == 1 else "✅ LOW RISK"
        
        st.subheader(f"Result: {result_text}")

        # 2. Save to PostgreSQL
        history_df = pd.DataFrame([{
            "loan_duration": duration,
            "amount": amount,
            "prediction": result_text,
            "created_at": datetime.datetime.now()
        }])
        history_df.to_sql('loan_history', engine, if_exists='append', index=False)
        st.info("Transaction logged to database.")

elif page == "Business Dashboard":
    st.header("Executive Business Overview")
    
    try:
        # 1. Fetch data from PostgreSQL
        df = pd.read_sql("SELECT * FROM loan_history", engine)
        df['created_at'] = pd.to_datetime(df['created_at']) # Ensure date format
        
        if not df.empty:
            # --- KPI CALCULATIONS ---
            total_customers = len(df)
            defaults = len(df[df['prediction'].str.contains("HIGH RISK")])
            non_defaults = total_customers - defaults
            default_rate = (defaults / total_customers) * 100 if total_customers > 0 else 0

            # --- TOP ROW: 3 KPIs ---
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total Applications", f"{total_customers}")
            kpi2.metric("Defaults vs Non-Defaults", f"{defaults} / {non_defaults}")
            kpi3.metric("Default Percentage", f"{default_rate:.1f}%", delta=f"{default_rate:.1f}%", delta_color="inverse")

            st.divider()

            # --- MIDDLE ROW: Charts ---
            col_a, col_b = st.columns(2)

            with col_a:
                st.subheader("Distribution of Risk")
                risk_counts = df['prediction'].value_counts()
                st.bar_chart(risk_counts)

            with col_b:
                st.subheader("Loan Amounts (Histogram)")
                # A histogram of the 'amount' column
                st.bar_chart(df['amount'].value_counts().sort_index()) 

            # --- BOTTOM ROW: Time Series ---
            st.subheader("Loan Volume Over Time (Line Chart)")
            # Resample data by Day/Hour to show trends
            time_series = df.set_index('created_at').resample('D').size()
            st.line_chart(time_series)

        else:
            st.warning("No data found. Please run some predictions in the first tab!")
            
    except Exception as e:
        st.error(f"Error loading dashboard: {e}")