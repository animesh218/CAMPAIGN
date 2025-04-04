import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io

st.set_page_config(page_title="Campaign Analysis Dashboard", layout="wide")

st.title("Campaign Analysis Dashboard")

# File upload
uploaded_file = st.file_uploader("Upload your campaign CSV file", type=["csv"])

# Define constants that were previously in sidebar
PAGE_CAPACITY = 1500000  # Default page capacity
sla_threshold = 90  # Default SLA breach threshold

if uploaded_file is not None:
    # Process the data
    try:
        # Load CSV
        df = pd.read_csv(uploaded_file)
        
        # Convert date columns to datetime with flexible parsing
        date_columns = ['Goal Start Date', 'Goal End Date', 'Created Time']
        
        for col in date_columns:
            if col in df.columns:
                try:
                    # Try to convert with automatic format detection
                    df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
                    
                    # Check if any dates were not parsed correctly
                    if df[col].isna().any():
                        st.warning(f"Some {col} dates could not be parsed. Please ensure dates are in a standard format.")
                except Exception as e:
                    st.error(f"Error parsing {col}: {e}")
                    st.stop()
        
        # Add Overbooking Flag
        df['Overbooking'] = False
        grouped = df.groupby(['Page', 'Property', 'Goal Start Date', 'Goal End Date'])['Booked Impressions'].sum().reset_index()
        
        # Check overbooking per group
        grouped['Overbooking'] = grouped['Booked Impressions'] > PAGE_CAPACITY
        
        # Merge back to main df
        df = df.merge(grouped[['Page', 'Property', 'Goal Start Date', 'Goal End Date', 'Overbooking']],
                    on=['Page', 'Property', 'Goal Start Date', 'Goal End Date'], how='left', suffixes=('', '_grouped'))
        
        # Add Underdelivery flag
        df['Underdelivery'] = df['Delivered Impressions'] < df['Booked Impressions']
        
        # SLA Breach: under threshold% delivery or late start
        df['SLA_Breach'] = (
            (df['Delivered Impressions'] < (sla_threshold/100) * df['Booked Impressions']) |
            (df['Created Time'] > df['Goal Start Date'])
        )
        
        # Calculate overall fill rate
        total_booked = df['Booked Impressions'].sum()
        total_delivered = df['Delivered Impressions'].sum()
        fill_rate = (total_delivered / total_booked * 100) if total_booked > 0 else 0
        
        # Display overall fill rate prominently
        st.header("Overall Campaign Performance")
        st.metric("Overall Fill Rate", f"{fill_rate:.2f}%", 
                 delta=f"{fill_rate - 100:.2f}%" if fill_rate != 100 else "On Target")
        
        # Display metrics
        st.header("Campaign Performance Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Campaigns", len(df))
        with col2:
            st.metric("Overbooking Issues", sum(df['Overbooking']))
        with col3:
            st.metric("Underdelivery Issues", sum(df['Underdelivery']))
        with col4:
            st.metric("SLA Breaches", sum(df['SLA_Breach']))
        
        # Display raw data
        st.header("Campaign Data")
        show_columns = ['Lead ID', 'Line item ID', 'Page', 'Property', 'Booked Impressions', 
                         'Delivered Impressions', 'Overbooking', 'Underdelivery', 'SLA_Breach']
        
        st.dataframe(df[show_columns])
        
        # Download processed data
        output = io.BytesIO()
        df[show_columns].to_csv(output, index=False)
        output.seek(0)
        
        st.download_button(
            label="Download data as CSV",
            data=output,
            file_name="campaign_analysis_output.csv",
            mime="text/csv"
        )
        
        # True/False Analysis
        st.header("True/False Analysis")
        
        # Create tabs for different analyses
        tab1, tab2, tab3 = st.tabs(["Issue Distribution", "Page Analysis", "Property Analysis"])
        
        with tab1:
            col1, col2 = st.columns(2)
            
            with col1:
                # Count True/False for each flag
                flag_counts = pd.DataFrame({
                    'Status': ['True', 'False'],
                    'Overbooking': [sum(df['Overbooking']), len(df) - sum(df['Overbooking'])],
                    'Underdelivery': [sum(df['Underdelivery']), len(df) - sum(df['Underdelivery'])],
                    'SLA_Breach': [sum(df['SLA_Breach']), len(df) - sum(df['SLA_Breach'])]
                })
                
                # Convert to long format for plotting
                flag_counts_long = pd.melt(flag_counts, id_vars=['Status'], 
                                         value_vars=['Overbooking', 'Underdelivery', 'SLA_Breach'],
                                         var_name='Issue Type', value_name='Count')
                
                # Plot stacked bar chart
                fig = px.bar(flag_counts_long, x='Issue Type', y='Count', color='Status',
                             title='Issue Distribution (True/False)',
                             color_discrete_map={'True': 'red', 'False': 'green'})
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Calculate percentage of true values for each issue
                true_percentages = pd.DataFrame({
                    'Issue Type': ['Overbooking', 'Underdelivery', 'SLA_Breach'],
                    'Percentage': [
                        sum(df['Overbooking']) / len(df) * 100,
                        sum(df['Underdelivery']) / len(df) * 100,
                        sum(df['SLA_Breach']) / len(df) * 100
                    ]
                })
                
                fig = px.pie(true_percentages, values='Percentage', names='Issue Type',
                            title='Distribution of Issues (% of Total Campaigns)')
                st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            # Page-wise analysis
            st.subheader("Page-wise Analysis")
            
            # Create metrics by page
            page_metrics = df.groupby('Page').agg({
                'Booked Impressions': 'sum',
                'Delivered Impressions': 'sum',
                'Lead ID': 'count',
                'Overbooking': 'mean',
                'Underdelivery': 'mean',
                'SLA_Breach': 'mean'
            }).reset_index()
            
            # Calculate fill rate for each page
            page_metrics['Fill Rate'] = (page_metrics['Delivered Impressions'] / page_metrics['Booked Impressions'] * 100).round(2)
            
            # Rename columns for display
            page_metrics = page_metrics.rename(columns={
                'Lead ID': 'Campaign Count',
                'Overbooking': 'Overbooking Rate',
                'Underdelivery': 'Underdelivery Rate',
                'SLA_Breach': 'SLA Breach Rate'
            })
            
            # Convert rates to percentages
            for col in ['Overbooking Rate', 'Underdelivery Rate', 'SLA Breach Rate']:
                page_metrics[col] = (page_metrics[col] * 100).round(2)
            
            # Display table
            st.dataframe(page_metrics)
            
            # Create visualizations
            col1, col2 = st.columns(2)
                
            with col1:
                # Page Fill Rate
                fig = px.bar(page_metrics, x='Page', y='Fill Rate',
                            title='Fill Rate by Page (%)',
                            color='Fill Rate',
                            color_continuous_scale='RdYlGn',
                            text_auto='.2f')
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                fig.update_layout(yaxis_range=[0, max(120, page_metrics['Fill Rate'].max() * 1.1)])
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Issue Rates by Page
                page_issues = pd.melt(page_metrics, 
                                    id_vars=['Page'], 
                                    value_vars=['Overbooking Rate', 'Underdelivery Rate', 'SLA Breach Rate'],
                                    var_name='Issue Type', value_name='Rate')
                
                fig = px.bar(page_issues, x='Page', y='Rate', color='Issue Type',
                            title='Issue Rates by Page (%)',
                            barmode='group',
                            text_auto='.2f')
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
        
        with tab3:
            # Property-wise analysis
            st.subheader("Property-wise Analysis")
            
            # Create metrics by property
            property_metrics = df.groupby('Property').agg({
                'Booked Impressions': 'sum',
                'Delivered Impressions': 'sum',
                'Lead ID': 'count',
                'Overbooking': 'mean',
                'Underdelivery': 'mean',
                'SLA_Breach': 'mean'
            }).reset_index()
            
            # Calculate fill rate for each property
            property_metrics['Fill Rate'] = (property_metrics['Delivered Impressions'] / property_metrics['Booked Impressions'] * 100).round(2)
            
            # Rename columns for display
            property_metrics = property_metrics.rename(columns={
                'Lead ID': 'Campaign Count',
                'Overbooking': 'Overbooking Rate',
                'Underdelivery': 'Underdelivery Rate',
                'SLA_Breach': 'SLA Breach Rate'
            })
            
            # Convert rates to percentages
            for col in ['Overbooking Rate', 'Underdelivery Rate', 'SLA Breach Rate']:
                property_metrics[col] = (property_metrics[col] * 100).round(2)
            
            # Display table
            st.dataframe(property_metrics)
            
            # Create visualizations
            col1, col2 = st.columns(2)
                
            with col1:
                # Property Fill Rate
                fig = px.bar(property_metrics, x='Property', y='Fill Rate',
                            title='Fill Rate by Property (%)',
                            color='Fill Rate',
                            color_continuous_scale='RdYlGn',
                            text_auto='.2f')
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                fig.update_layout(yaxis_range=[0, max(120, property_metrics['Fill Rate'].max() * 1.1)])
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Issue Rates by Property
                property_issues = pd.melt(property_metrics, 
                                    id_vars=['Property'], 
                                    value_vars=['Overbooking Rate', 'Underdelivery Rate', 'SLA Breach Rate'],
                                    var_name='Issue Type', value_name='Rate')
                
                fig = px.bar(property_issues, x='Property', y='Rate', color='Issue Type',
                            title='Issue Rates by Property (%)',
                            barmode='group',
                            text_auto='.2f')
                fig.update_traces(texttemplate='%{text}%', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
    
    except Exception as e:
        st.error(f"Error processing data: {e}")
        st.write("Please make sure your CSV file has the required columns:")
        st.write("- Lead ID\n- Line item ID\n- Page\n- Property\n- Booked Impressions\n- Delivered Impressions\n- Goal Start Date\n- Goal End Date\n- Created Time")
        
        st.error("Date format issue detected. Your dates should be in a standard format like:")
        st.write("- DD-MM-YYYY (e.g., 13-01-2025)")
        st.write("- MM-DD-YYYY (e.g., 01-13-2025)")
        st.write("- YYYY-MM-DD (e.g., 2025-01-13)")

else:
    st.info("Please upload a CSV file to analyze campaign performance.")
    
    # Sample data structure
    st.header("Expected Data Format")
    sample_data = {
        'Lead ID': ['L001', 'L002', 'L003'],
        'Line item ID': ['LI001', 'LI002', 'LI003'],
        'Page': ['Homepage', 'Article', 'Homepage'],
        'Property': ['Website A', 'Website B', 'Website A'],
        'Booked Impressions': [500000, 700000, 400000],
        'Delivered Impressions': [450000, 600000, 350000],
        'Goal Start Date': ['13-01-2025', '15-01-2025', '01-02-2025'],
        'Goal End Date': ['31-01-2025', '15-02-2025', '28-02-2025'],
        'Created Time': ['25-12-2024', '14-01-2025', '30-01-2025']
    }
    
    st.dataframe(pd.DataFrame(sample_data))