# 科技自主创新政策实证研究 — v4 报告

## 数据概况

- v4 扩展样本 (2017-2024): 37,697 obs × 5,713 firms
- v3 基准样本 (2017-2022): 26,772 obs × 5,404 firms
- 制造业占比: 63.8%
- 省份覆盖率: 97.0%

## baseline

| Model | Variable | Coef | SE | p | N |
|-------|----------|------|-----|---|--|
| M1_Baseline_DID | manufacturing_post2021 | -0.0409 * | 0.0221 | 0.0643 | 37694 |
| M1b_DID_ctrl_post2023 | manufacturing_post2021 | -0.0409 * | 0.0221 | 0.0643 | 37694 |
| M1_Baseline_DID | manufacturing_post2021 | -0.0238 | 0.0234 | 0.3095 | 26770 |
| M1b_DID_ctrl_post2023 | manufacturing_post2021 | -0.0238 | 0.0234 | 0.3095 | 26770 |
| M1_Baseline_DID | manufacturing_post2021 | -0.0232 | 0.0232 | 0.3164 | 30205 |
| M1b_DID_ctrl_post2023 | manufacturing_post2021 | -0.0232 | 0.0232 | 0.3164 | 30205 |

## mechanism

| Model | Variable | Coef | SE | p | N |
|-------|----------|------|-----|---|--|
| M2a_RD_intensity | manufacturing_post2021 | -0.1924 | 0.1268 | 0.1293 | 32893 |
| M2b_RD_staff | manufacturing_post2021 | -0.0733 * | 0.0427 | 0.0862 | 37694 |
| M2c_subsidy_channel | manufacturing_post2021 | -0.0404 * | 0.0221 | 0.0681 | 37694 |
| M2d_policy_exposure | manufacturing_post2021 | -0.0443 * | 0.0266 | 0.0963 | 30184 |
| M2a_RD_intensity | manufacturing_post2021 | -0.2852 ** | 0.1269 | 0.0246 | 22829 |
| M2b_RD_staff | manufacturing_post2021 | -0.1381 *** | 0.0417 | 0.0009 | 26770 |
| M2c_subsidy_channel | manufacturing_post2021 | -0.0226 | 0.0235 | 0.3367 | 26770 |
| M2d_policy_exposure | manufacturing_post2021 | -0.0223 | 0.0278 | 0.4216 | 22342 |
| M2a_RD_intensity | manufacturing_post2021 | -0.2879 ** | 0.1289 | 0.0256 | 25364 |
| M2b_RD_staff | manufacturing_post2021 | -0.1596 *** | 0.0430 | 0.0002 | 30205 |
| M2c_subsidy_channel | manufacturing_post2021 | -0.0232 | 0.0233 | 0.3195 | 30205 |
| M2d_policy_exposure | manufacturing_post2021 | -0.0213 | 0.0276 | 0.4395 | 25275 |

## robustness

| Model | Variable | Coef | SE | p | N |
|-------|----------|------|-----|---|--|
| M3a_grant | manufacturing_post2021 | 0.0119 | 0.0210 | 0.5728 | 37694 |
| M3b_patent_apply | manufacturing_post2021 | -0.0319 | 0.0291 | 0.2728 | 37694 |
| M3c_patent_grant | manufacturing_post2021 | -0.0029 | 0.0319 | 0.9279 | 37694 |
| M3a_grant | manufacturing_post2021 | -0.0044 | 0.0218 | 0.8412 | 26770 |
| M3b_patent_apply | manufacturing_post2021 | -0.0002 | 0.0323 | 0.9963 | 26770 |
| M3c_patent_grant | manufacturing_post2021 | 0.0431 | 0.0340 | 0.2053 | 26770 |
| M3a_grant | manufacturing_post2021 | -0.0046 | 0.0216 | 0.8308 | 30205 |
| M3b_patent_apply | manufacturing_post2021 | -0.0119 | 0.0323 | 0.7115 | 30205 |
| M3c_patent_grant | manufacturing_post2021 | 0.0404 | 0.0338 | 0.2323 | 30205 |
| ROB_drop2024 | manufacturing_post2021 | -0.0291 | 0.0223 | 0.1929 | 32210 |

## placebo

| Model | Variable | Coef | SE | p | N |
|-------|----------|------|-----|---|--|
| M4a_placebo_2019 | manufacturing_post2019 | 0.0254 | 0.0252 | 0.3141 | 16480 |
| M4b_placebo_2020 | manufacturing_post2020 | 0.0304 | 0.0280 | 0.2776 | 16480 |
| M4a_placebo_2019 | manufacturing_post2019 | 0.0254 | 0.0252 | 0.3141 | 16480 |
| M4b_placebo_2020 | manufacturing_post2020 | 0.0304 | 0.0280 | 0.2776 | 16480 |

## event_study

| Model | Variable | Coef | SE | p | N |
|-------|----------|------|-----|---|--|
| M5_event_study | event_m4 | 0.0237 | 0.0309 | 0.4437 | 37694 |
| M5_event_study | event_m3 | -0.0134 | 0.0283 | 0.6353 | 37694 |
| M5_event_study | event_m2 | 0.0004 | 0.0283 | 0.9878 | 37694 |
| M5_event_study | event_p0 | -0.0265 | 0.0248 | 0.2848 | 37694 |
| M5_event_study | event_p1 | -0.0320 | 0.0277 | 0.2484 | 37694 |
| M5_event_study | event_p2 | -0.0298 | 0.0286 | 0.2968 | 37694 |
| M5_event_study | event_p3 | -0.0695 ** | 0.0348 | 0.0457 | 37694 |
| M5_event_study | event_m4 | 0.0029 | 0.0318 | 0.9262 | 26770 |
| M5_event_study | event_m3 | -0.0345 | 0.0297 | 0.2453 | 26770 |
| M5_event_study | event_m2 | -0.0150 | 0.0290 | 0.6037 | 26770 |
| M5_event_study | event_p0 | -0.0330 | 0.0263 | 0.2084 | 26770 |
| M5_event_study | event_p1 | -0.0351 | 0.0298 | 0.2375 | 26770 |

## provincial_fiscal

| Model | Variable | Coef | SE | p | N |
|-------|----------|------|-----|---|--|
| P1_prov_sci_tech_interact | manufacturing_post2021 | -0.0487 | 0.0450 | 0.2785 | 36569 |
| P1_prov_sci_tech_interact | did_x_prov_sci_tech | 0.0006 | 0.0096 | 0.9474 | 36569 |
| P2_prov_rd_intensity_interact | manufacturing_post2021 | -0.0323 | 0.0514 | 0.5290 | 35636 |
| P2_prov_rd_intensity_interact | did_x_prov_rd_intensity | -0.0042 | 0.0164 | 0.8004 | 35636 |
| P3_prov_sci_exp_interact | manufacturing_post2021 | -0.0875 | 0.1043 | 0.4014 | 36569 |
| P3_prov_sci_exp_interact | did_x_ln_prov_sci | 0.0070 | 0.0173 | 0.6876 | 36569 |
| P4_triple_diff_high_sci_prov | manufacturing_post2021 | -0.0357 | 0.0276 | 0.1956 | 37694 |
| P4_triple_diff_high_sci_prov | did_x_high_sci_prov | -0.0096 | 0.0317 | 0.7621 | 37694 |
| P4_triple_diff_high_sci_prov | high_sci_tech_province | 0.0042 | 0.0227 | 0.8546 | 37694 |
| P5_High_sci_tech_prov_subsample | manufacturing_post2021 | -0.0534 | 0.0344 | 0.1207 | 20249 |
| P5_Low_sci_tech_prov_subsample | manufacturing_post2021 | -0.0207 | 0.0320 | 0.5187 | 17445 |
| P1_prov_sci_tech_interact | manufacturing_post2021 | -0.0310 | 0.0474 | 0.5133 | 25813 |
| P1_prov_sci_tech_interact | did_x_prov_sci_tech | 0.0012 | 0.0104 | 0.9090 | 25813 |
| P2_prov_rd_intensity_interact | manufacturing_post2021 | -0.0079 | 0.0497 | 0.8730 | 25813 |
| P2_prov_rd_intensity_interact | did_x_prov_rd_intensity | -0.0066 | 0.0159 | 0.6793 | 25813 |
| P3_prov_sci_exp_interact | manufacturing_post2021 | -0.0723 | 0.1047 | 0.4896 | 25813 |
| P3_prov_sci_exp_interact | did_x_ln_prov_sci | 0.0078 | 0.0176 | 0.6583 | 25813 |
| P4_triple_diff_high_sci_prov | manufacturing_post2021 | -0.0236 | 0.0292 | 0.4190 | 26770 |
| P4_triple_diff_high_sci_prov | did_x_high_sci_prov | -0.0012 | 0.0339 | 0.9707 | 26770 |
| P4_triple_diff_high_sci_prov | high_sci_tech_province | 0.0064 | 0.0233 | 0.7828 | 26770 |
| P5_High_sci_tech_prov_subsample | manufacturing_post2021 | -0.0312 | 0.0374 | 0.4040 | 13483 |
| P5_Low_sci_tech_prov_subsample | manufacturing_post2021 | -0.0088 | 0.0332 | 0.7905 | 13287 |

## v4 新增分析

- **省级财政交互**: DID × 省财政科技支出占比，检验地方财政科技投入的调节效应
- **时间窗口扩展**: 从 2017-2022 扩展到 2017-2024，捕捉政策的长期效应
- **2023年稀释控制**: 加入 post2023 虚拟变量控制全行业100%加计扣除的稀释效应