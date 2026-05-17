# R fixest script for V6 Efficiency Analysis
library(fixest)
library(data.table)

df <- fread("../v5/data/v5_clean_panel.csv")
df_2017_2022 <- df[year >= 2017 & year <= 2022]

# Baseline efficiency
m1 <- feols(eff_invention_apply_rd_10k ~ manufacturing_post2021 + ln_assets + roa + cashflow_ratio + firm_age | stock_code + year, cluster = ~stock_code, data = df_2017_2022)
m2 <- feols(eff_invention_grant_rd_10k ~ manufacturing_post2021 + ln_assets + roa + cashflow_ratio + firm_age | stock_code + year, cluster = ~stock_code, data = df_2017_2022)
m3 <- feols(eff_invention_apply_staff ~ manufacturing_post2021 + ln_assets + roa + cashflow_ratio + firm_age | stock_code + year, cluster = ~stock_code, data = df_2017_2022)
m4 <- feols(eff_invention_grant_staff ~ manufacturing_post2021 + ln_assets + roa + cashflow_ratio + firm_age | stock_code + year, cluster = ~stock_code, data = df_2017_2022)

etable(m1, m2, m3, m4, cluster = ~stock_code)

# R&D Behavior
m5 <- feols(ln_rd_expense_10k ~ manufacturing_post2021 + ln_assets + roa + cashflow_ratio + firm_age | stock_code + year, cluster = ~stock_code, data = df_2017_2022)
m6 <- feols(ln_rd_staff ~ manufacturing_post2021 + ln_assets + roa + cashflow_ratio + firm_age | stock_code + year, cluster = ~stock_code, data = df_2017_2022)

summary(m5)
summary(m6)
