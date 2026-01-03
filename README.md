# Veefyed – Senior Data Assessment (Day 1 & Day 2)

This repository contains my submission for the **Veefyed Senior Data Analyst technical assessment**, covering **Day 1 (Scraping & Structuring)** and **Day 2 (API Enrichment)**.

---

## Objective
To extract, clean, structure, and enrich real-world skincare product data, demonstrating data acquisition, validation, enrichment, and reliability assessment workflows.

---

## Day 1 – Scrape & Structure Skincare Product Data

### Scope
- Source: https://qudobeauty.com/
- Scraped **25 skincare products** (within the required 20–30 range)
- Data was structured into an analysis-ready CSV without inferring missing values

### Fields Extracted
- Product name  
- Brand  
- Category / type  
- Ingredients (when available)  
- Size / packaging  
- Product image URL  
- Product page URL  

### How to Run
 Day 1 – Scraping
-pip3 install requests beautifulsoup4 pandas
-python3 scripts/scrape_qudo.py

### Outputs
- `data/qudo_skincare_day1_final.csv`
- Day 1 documentation (methodology, assumptions, limitations)
 

## Day 2 – Google Custom Search API Enrichment

### Scope
- **10 products** selected from the Day 1 final dataset
- Enriched using the **Google Custom Search JSON API**
- At least **one authenticated API call per product**

### Enrichment Focus
- Manufacturer or official product pages
- External source validation
- Supplementary product context
- Reliability and confidence assessment

### API Usage
- API: Google Custom Search JSON API
- Endpoint: `https://customsearch.googleapis.com/customsearch/v1`
- Credentials managed via environment variables (`.env`)
- API calls validated programmatically using HTTP status checks

### Enrichment Outputs
Additional columns added to the dataset include:
- API query and engine metadata
- Official product page and title
- External source references
- Reliability score (0–100)
- Confidence label (High / Medium / Low)
- API error logging (if applicable)

### How to Run
 Day 2 – Enrichment
-pip3 install requests pandas python-dotenv
-python3 scripts/enrich_day2_google_cse.py


### Outputs
- `data/qudo_skincare_day2_enriched_final.csv`

