# 科技自主创新政策实证研究报告

## 一、数据与样本

- 基准样本: 2017-2022, 128,483 obs × 5,407 firms
- 处理组 (制造业): 80,081, 对照组 (非制造业): 48,402
- 政策冲击: 2021 年制造业研发费用加计扣除比例从 75% 提高至 100%

## 二、基准 DID 结果

- manufacturing_post2021: coef=-0.0303, se=0.0233, p=0.1923, n=124,337, firms=5,262
- manufacturing_post2021: coef=-0.0301, se=0.0232, p=0.1948, n=127,617, firms=5,265
- manufacturing_post2021: coef=-0.0509, se=0.0228, p=0.0255**, n=177,645, firms=5,629
- manufacturing_post2021: coef=-0.0573, se=0.0236, p=0.0152**, n=141,790, firms=5,606

## 三、机制检验

- M3a_RD_intensity: coef=-0.0631, se=0.2405, p=0.7930
- M3b_RD_staff: coef=-0.1871, se=0.0400, p=0.0000***
- M3c_rd_subsidy_channel: coef=-0.0289, se=0.0233, p=0.2151
- M3a_RD_intensity: coef=-0.1070, se=0.2395, p=0.6551
- M3b_RD_staff: coef=-0.1936, se=0.0404, p=0.0000***
- M3c_rd_subsidy_channel: coef=-0.0290, se=0.0233, p=0.2132
- M3a_RD_intensity: coef=-0.1551, se=0.2543, p=0.5419
- M3b_RD_staff: coef=-0.1895, se=0.0397, p=0.0000***
- M3c_rd_subsidy_channel: coef=-0.0509, se=0.0228, p=0.0257**
- M3a_RD_intensity: coef=-0.3563, se=0.2557, p=0.1636
- M3b_RD_staff: coef=-0.1236, se=0.0351, p=0.0004***
- M3c_rd_subsidy_channel: coef=-0.0583, se=0.0236, p=0.0134**

## 四、稳健性检验

- M5a_drop2024 (manufacturing_post2021): coef=-0.0303, se=0.0233, p=0.1923
- M5b_ctrl_post2023 (manufacturing_post2021): coef=-0.0303, se=0.0233, p=0.1923
- M5c_placebo_post2020 (manufacturing_post2020): coef=-0.0174, se=0.0232, p=0.4539
- M5a_drop2024 (manufacturing_post2021): coef=-0.0301, se=0.0232, p=0.1948
- M5b_ctrl_post2023 (manufacturing_post2021): coef=-0.0301, se=0.0232, p=0.1948
- M5c_placebo_post2020 (manufacturing_post2020): coef=-0.0175, se=0.0231, p=0.4470
- M5a_drop2024 (manufacturing_post2021): coef=-0.0374, se=0.0226, p=0.0982*
- M5b_ctrl_post2023 (manufacturing_post2021): coef=-0.0509, se=0.0228, p=0.0255**
- M5c_placebo_post2020 (manufacturing_post2020): coef=-0.0404, se=0.0226, p=0.0738*
- M5a_drop2024 (manufacturing_post2021): coef=-0.0457, se=0.0236, p=0.0526*
- M5b_ctrl_post2023 (manufacturing_post2021): coef=-0.0573, se=0.0236, p=0.0152**
- M5c_placebo_post2020 (manufacturing_post2020): coef=-0.0447, se=0.0254, p=0.0782*

## 五、事件研究

| 变量 | 系数 | 标准误 | p值 |
|------|------|--------|-----|
| event_pre_4 | 0.0080 | 0.0321 | 0.8021 |
| event_pre_3 | -0.0268 | 0.0296 | 0.3653 |
| event_pre_2 | 0.0067 | 0.0277 | 0.8078 |
| event_post_0 | -0.0331 | 0.0260 | 0.2028 |
| event_post_1 | -0.0328 | 0.0293 | 0.2631 |
| ln_assets | 0.0344 | 0.0198 | 0.0812* |
| roa | 0.0066 | 0.0644 | 0.9178 |
| firm_age | 0.0350 | 0.0571 | 0.5394 |
| event_pre_4 | 0.0056 | 0.0295 | 0.8488 |
| event_pre_3 | -0.0285 | 0.0274 | 0.2977 |
| event_pre_2 | 0.0052 | 0.0264 | 0.8422 |
| event_post_0 | -0.0341 | 0.0251 | 0.1743 |
| event_post_1 | -0.0335 | 0.0283 | 0.2372 |
| ln_assets | 0.0305 | 0.0192 | 0.1126 |
| roa | 0.0207 | 0.0636 | 0.7444 |
| firm_age | 0.0354 | 0.0553 | 0.5221 |
| event_pre_4 | 0.0265 | 0.0324 | 0.4132 |
| event_pre_3 | -0.0083 | 0.0294 | 0.7786 |
| event_pre_2 | 0.0217 | 0.0281 | 0.4400 |
| event_post_0 | -0.0308 | 0.0258 | 0.2321 |
| event_post_1 | -0.0328 | 0.0288 | 0.2554 |
| event_post_2 | -0.0302 | 0.0301 | 0.3159 |
| event_post_3 | -0.0771 | 0.0364 | 0.0342** |
| ln_assets | 0.0490 | 0.0161 | 0.0023*** |
| roa | 0.0365 | 0.0622 | 0.5574 |
| firm_age | 0.0105 | 0.0378 | 0.7805 |
| event_pre_2 | 0.0226 | 0.0281 | 0.4220 |
| event_post_0 | -0.0312 | 0.0257 | 0.2239 |
| event_post_1 | -0.0359 | 0.0286 | 0.2101 |
| event_post_2 | -0.0365 | 0.0303 | 0.2285 |
| event_post_3 | -0.0877 | 0.0368 | 0.0170** |
| ln_assets | 0.0961 | 0.0195 | 0.0000*** |
| roa | 0.0011 | 0.0643 | 0.9859 |
| firm_age | -0.0336 | 0.0394 | 0.3928 |

## 六、结论约束

- 不得把 `tax_saving_est` 写成真实税收优惠数据，该变量是 `RDSpendSum × rd_deduction_rate × 0.25` 的估算值。
- 不得把累计专利存量 (`invention_cum_*`) 解释为当年创新产出。
- 因变量使用 `ln(1 + invention_apply)` 即当年发明专利申请的流量指标。
- 如果基准 DID 不显著，如实报告，不得修改模型追求显著性。
- 2023-2024 年全行业加计扣除比例均提高至 100%，制造业_post2021 效应可能被稀释。
- SOE 变量覆盖率仅 27%，异质性分析为子样本结果，不具全样本代表性。