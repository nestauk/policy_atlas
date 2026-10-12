# Pool orderings: How effective are retail health targets (healthier food sales targets for supermarkets and food retailers) at reducing obesity?

Run 2026-10-12T14:08:55+00:00. Depth `rapid`, cap 100. Pool 598 papers (593 distinct papers) from 23 query calls. No ground truth; this compares orderings of one pool.

## Where the probe papers rank

| paper | baseline | reserve | hits | rrf | blend | mix_c | mix_q | mix_f1 | mix |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| What is the effectiveness of obesity related interventions at retail g | 9 | 3 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| Can Healthy Checkout Counters Improve Food Purchases? Two Real-Life Ex | 73 | 120 | 263 | 263 | 160 | 69 | 321 | 231 | 87 |
| Retail Marketing Strategies, Purchasing, and Prices: A Scoping Review  | 489 | 16 | 20 | 19 | 38 | 57 | 15 | 15 | 21 |
| Supermarkets, Other Food Stores, and Obesity | 23 | 71 | 219 | 219 | 81 | 2 | 2 | 2 | 2 |

A number at or under 100 means the paper survives the cut at this scope.

## What the top 100 looks like

| ordering | overlap with baseline | median_year | share_from_2020 | median_cited_by | share_two_plus_queries | share_no_query | origins |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline | 100 | 2019.5 | 0.5 | 15.5 | 0.07 | 0.81 | {'snowball_forward': 66, 'variant_sr': 1, 'semantic': 12, 'generated': 2, 'snowball_backward': 19} |
| reserve | 53 | 2018.5 | 0.43 | 9.0 | 0.37 | 0.44 | {'variant_sr': 13, 'generated': 27, 'variant_rct': 10, 'snowball_forward': 36, 'semantic': 6, 'snowball_backward': 8} |
| hits | 19 | 2016.0 | 0.3 | 9.0 | 0.87 | 0.0 | {'variant_sr': 20, 'generated': 17, 'variant_rct': 10, 'semantic': 49, 'snowball_forward': 4} |
| rrf | 10 | 2016.0 | 0.29 | 9.0 | 0.87 | 0.0 | {'variant_sr': 20, 'generated': 22, 'variant_rct': 10, 'semantic': 47, 'snowball_forward': 1} |
| blend | 45 | 2018.0 | 0.39 | 11.0 | 0.58 | 0.27 | {'variant_sr': 10, 'generated': 10, 'snowball_forward': 27, 'variant_rct': 8, 'semantic': 42, 'snowball_backward': 3} |
| mix_c | 49 | 2016.0 | 0.33 | 54.0 | 0.39 | 0.5 | {'variant_sr': 7, 'snowball_backward': 28, 'generated': 7, 'variant_rct': 6, 'snowball_forward': 24, 'semantic': 28} |
| mix_q | 21 | 2014.0 | 0.33 | 19.5 | 0.6 | 0.28 | {'variant_sr': 13, 'snowball_backward': 28, 'generated': 16, 'variant_rct': 8, 'semantic': 34, 'snowball_forward': 1} |
| mix_f1 | 24 | 2014.5 | 0.33 | 22.0 | 0.6 | 0.28 | {'variant_sr': 14, 'snowball_backward': 28, 'generated': 13, 'variant_rct': 8, 'semantic': 36, 'snowball_forward': 1} |
| mix | 42 | 2015.0 | 0.33 | 43.5 | 0.47 | 0.44 | {'variant_sr': 9, 'snowball_backward': 28, 'generated': 8, 'variant_rct': 7, 'semantic': 31, 'snowball_forward': 17} |

## Top 15 under `baseline`

1. 2025 · Health promotion through in-store communication: a systematic literature review of real environment experiments · cited 0 · queries 0 · inset 0 · wcoup 28.076 · spec 16.0 · snowball_forward
2. 2021 · Retail Strategies to Support Healthy Eating · cited 1 · queries 0 · inset 0 · wcoup 23.677 · spec 10.563 · snowball_forward
3. 2018 · La méthode du marketing social appliquée à une intervention nutritionnelle en magasin · cited 0 · queries 0 · inset 0 · wcoup 27.192 · spec 10.0 · snowball_forward
4. 2020 · Retail Nutrition Programs and Outcomes: An Evidence Analysis Center Scoping Review · cited 17 · queries 0 · inset 0 · wcoup 29.884 · spec 8.384 · snowball_forward
5. 2019 · A Systematic Review of the Effect of Retail Food Environment Interventions on Diet and Health with a Focus on the Enabling Role of Public Policies · cited 132 · queries 0 · inset 3 · wcoup 38.169 · spec 8.363 · snowball_forward
6. 2024 · Strategies associated with improved healthiness of consumer purchasing in supermarket interventions: a systematic overview of reviews and evaluation of primary articles · cited 4 · queries 0 · inset 0 · wcoup 22.338 · spec 7.853 · snowball_forward
7. 2022 · Encouraging Healthier Food and Beverage Purchasing and Consumption: A Review of Interventions within Grocery Retail Settings · cited 10 · queries 0 · inset 0 · wcoup 22.677 · spec 7.686 · snowball_forward
8. 2025 · Supermarkets, do they make the healthy choice the easy choice? A review of the healthfulness of the supermarket food environment · cited 5 · queries 0 · inset 0 · wcoup 11.508 · spec 7.652 · snowball_forward
9. 2016 · What is the effectiveness of obesity related interventions at retail grocery stores and supermarkets? —a systematic review · cited 199 · queries 7 · inset 7 · wcoup 25.455 · spec 7.327 · variant_sr
10. 2013 · Supermarket and Grocery Store–Based Interventions to Promote Healthful Food Choices and Eating Practices: A Systematic Review · cited 223 · queries 1 · inset 12 · wcoup 12.755 · spec 7.181 · semantic
11. 2016 · A Systematic Review of the Effectiveness of Supermarket-Based Interventions Involving Product, Promotion, or Place on the Healthiness of Consumer Purchases · cited 147 · queries 1 · inset 6 · wcoup 24.215 · spec 6.831 · semantic
12. 2016 · Healthy Food Environment Scoping Review · cited 3 · queries 0 · inset 0 · wcoup 10.455 · spec 6.284 · snowball_forward
13. 2026 · Healthy Eating Interventions in Convenience Stores and Diet‐Related Outcomes: A Systematic Review · cited 0 · queries 0 · inset 0 · wcoup 14.793 · spec 6.0 · snowball_forward
14. 2026 · Sustaining Health Promotion in Australian Supermarkets: Qualitative Perspectives From the Reach for the Stars Programme · cited 0 · queries 0 · inset 0 · wcoup 12.415 · spec 6.0 · snowball_forward
15. 2016 · Influência dos supermercados na disponibilidade e preço de alimentos ultraprocessados consumidos no Brasil · cited 1 · queries 0 · inset 0 · wcoup 14.208 · spec 5.762 · snowball_forward

## Top 15 under `reserve`

1. 2014 · Essays on community based behavior change interventions for obesity prevention · cited 0 · queries 2 · inset 0 · wcoup 3.7 · spec 1.0 · variant_sr
2. 2014 · Placement and promotion strategies to increase sales of healthier products in supermarkets in low-income, ethnically diverse neighborhoods: a randomized controlled trial · cited 177 · queries 3 · inset 9 · wcoup 12.723 · spec 5.722 · generated
3. 2016 · What is the effectiveness of obesity related interventions at retail grocery stores and supermarkets? —a systematic review · cited 199 · queries 7 · inset 7 · wcoup 25.455 · spec 7.327 · variant_sr
4. 2014 · A systematic review of the influence of the retail food environment around schools on obesity‐related outcomes · cited 194 · queries 2 · inset 0 · wcoup 0 · spec 0.0 · generated
5. 2012 · Sales effects of product health information at points of purchase: a systematic review · cited 57 · queries 3 · inset 4 · wcoup 3.0 · spec 2.738 · generated
6. 2015 · B’More healthy: retail rewards - design of a multi-level communications and pricing intervention to improve the food environment in Baltimore City · cited 36 · queries 3 · inset 1 · wcoup 6.87 · spec 1.804 · generated
7. 2018 · PROTOCOL: Effects of lifestyle modification interventions to prevent and manage child and adolescent obesity: a systematic review · cited 3 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
8. 2019 · Prioritizing Food Retailer Perspectives for Environmental Change in Food Stores to Encourage Healthy Dietary Purchases Among Low-Income Consumers in the United States · cited 0 · queries 2 · inset 0 · wcoup 0 · spec 0.0 · generated
9. 2018 · Calorie reduction programme launched · cited 1 · queries 3 · inset 1 · wcoup 0 · spec 0.96 · variant_rct
10. 2021 · Consider the Whole Picture When Discussing Infant Formula and Breast Milk · cited 7 · queries 4 · inset 0 · wcoup 0 · spec 0.0 · variant_sr
11. 2019 · Environmental interventions to reduce the consumption of sugar-sweetened beverages and their effects on health · cited 304 · queries 6 · inset 1 · wcoup 12.299 · spec 2.803 · variant_rct
12. 2020 · The healthy food marketing strategies study: design, baseline characteristics, and supermarket compliance. · cited 9 · queries 7 · inset 0 · wcoup 18.045 · spec 4.692 · generated
13. 2019 · The food environment in Latin America: a systematic review with a focus on environments relevant to obesity and related chronic diseases · cited 122 · queries 2 · inset 0 · wcoup 3.585 · spec 1.415 · variant_sr
14. 2022 · Talking about food sustainability · cited 0 · queries 2 · inset 0 · wcoup 0 · spec 0.0 · variant_sr
15. 2006 · Product/Process integration in food manufacture: Engineering sustained health · cited 102 · queries 1 · inset 1 · wcoup 0 · spec 0.488 · generated

## Top 15 under `hits`

1. 2016 · What is the effectiveness of obesity related interventions at retail grocery stores and supermarkets? —a systematic review · cited 199 · queries 7 · inset 7 · wcoup 25.455 · spec 7.327 · variant_sr
2. 2020 · The healthy food marketing strategies study: design, baseline characteristics, and supermarket compliance. · cited 9 · queries 7 · inset 0 · wcoup 18.045 · spec 4.692 · generated
3. 2019 · Environmental interventions to reduce the consumption of sugar-sweetened beverages and their effects on health · cited 304 · queries 6 · inset 1 · wcoup 12.299 · spec 2.803 · variant_rct
4. 2018 · Getting the balance right—tackling the obesogenic environment by reducing unhealthy options in a hospital shop without affecting profit · cited 13 · queries 6 · inset 1 · wcoup 0 · spec 0.734 · semantic
5. 2018 · PROTOCOL: Effects of lifestyle modification interventions to prevent and manage child and adolescent obesity: a systematic review · cited 3 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
6. 2016 · The impact of a pricing and communications intervention on stocking and sales of healthier foods in small Baltimore City food stores · cited 0 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
7. 2011 · Regulating Food Retail for Obesity Prevention: How Far Can Cities Go? · cited 16 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic
8. 2016 · The year in cardiology 2016: prevention · cited 1 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
9. 2019 · Sustainable livestock systems to improve human health, nutrition, and economic status · cited 103 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
10. 2000 · Changes in supermarket sales during and after a staged health promotion campaign · cited 11 · queries 5 · inset 1 · wcoup 1.585 · spec 1.513 · semantic
11. 2026 · P098 Investigation of the public’s drivers of food shopping choices and perspectives on the healthiness of supermarkets in England · cited 0 · queries 5 · inset 0 · wcoup 0 · spec 0.0 · generated
12. 2010 · Wanted: politicians to champion health (not obesity) · cited 8 · queries 5 · inset 0 · wcoup 0 · spec 0.0 · semantic
13. 2016 · What is the effectiveness of obesity related interventions at retail grocery stores and supermarkets? —a systematic review · cited 0 · queries 5 · inset 0 · wcoup 0 · spec 0.0 · semantic
14. 2022 · Food Sales and Adult Weight Status: Results of a Cross-Sectional Study in England · cited 2 · queries 4 · inset 0 · wcoup 7.129 · spec 2.78 · semantic
15. 2013 · Overweight and obesity: Can we reconcile evidence about supermarkets and fast food retailers for public health policy? · cited 26 · queries 4 · inset 1 · wcoup 9.093 · spec 2.57 · semantic

## Top 15 under `rrf`

1. 2016 · What is the effectiveness of obesity related interventions at retail grocery stores and supermarkets? —a systematic review · cited 199 · queries 7 · inset 7 · wcoup 25.455 · spec 7.327 · variant_sr
2. 2020 · The healthy food marketing strategies study: design, baseline characteristics, and supermarket compliance. · cited 9 · queries 7 · inset 0 · wcoup 18.045 · spec 4.692 · generated
3. 2018 · PROTOCOL: Effects of lifestyle modification interventions to prevent and manage child and adolescent obesity: a systematic review · cited 3 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
4. 2019 · Environmental interventions to reduce the consumption of sugar-sweetened beverages and their effects on health · cited 304 · queries 6 · inset 1 · wcoup 12.299 · spec 2.803 · variant_rct
5. 2011 · Regulating Food Retail for Obesity Prevention: How Far Can Cities Go? · cited 16 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic
6. 2018 · Getting the balance right—tackling the obesogenic environment by reducing unhealthy options in a hospital shop without affecting profit · cited 13 · queries 6 · inset 1 · wcoup 0 · spec 0.734 · semantic
7. 2016 · The impact of a pricing and communications intervention on stocking and sales of healthier foods in small Baltimore City food stores · cited 0 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
8. 2016 · The year in cardiology 2016: prevention · cited 1 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
9. 2019 · Sustainable livestock systems to improve human health, nutrition, and economic status · cited 103 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
10. 2000 · Changes in supermarket sales during and after a staged health promotion campaign · cited 11 · queries 5 · inset 1 · wcoup 1.585 · spec 1.513 · semantic
11. 2010 · Wanted: politicians to champion health (not obesity) · cited 8 · queries 5 · inset 0 · wcoup 0 · spec 0.0 · semantic
12. 2026 · P098 Investigation of the public’s drivers of food shopping choices and perspectives on the healthiness of supermarkets in England · cited 0 · queries 5 · inset 0 · wcoup 0 · spec 0.0 · generated
13. 2014 · Store Impulse Marketing Strategies and Body Mass Index · cited 63 · queries 4 · inset 2 · wcoup 0 · spec 1.073 · semantic
14. 2016 · What is the effectiveness of obesity related interventions at retail grocery stores and supermarkets? —a systematic review · cited 0 · queries 5 · inset 0 · wcoup 0 · spec 0.0 · semantic
15. 2014 · Buying Food on Sale: A Mixed Methods Study With Shoppers at an Urban Supermarket, Philadelphia, Pennsylvania, 2010–2012 · cited 19 · queries 4 · inset 1 · wcoup 7.401 · spec 2.051 · semantic

## Top 15 under `blend`

1. 2016 · What is the effectiveness of obesity related interventions at retail grocery stores and supermarkets? —a systematic review · cited 199 · queries 7 · inset 7 · wcoup 25.455 · spec 7.327 · variant_sr
2. 2020 · The healthy food marketing strategies study: design, baseline characteristics, and supermarket compliance. · cited 9 · queries 7 · inset 0 · wcoup 18.045 · spec 4.692 · generated
3. 2025 · Health promotion through in-store communication: a systematic literature review of real environment experiments · cited 0 · queries 0 · inset 0 · wcoup 28.076 · spec 16.0 · snowball_forward
4. 2019 · Environmental interventions to reduce the consumption of sugar-sweetened beverages and their effects on health · cited 304 · queries 6 · inset 1 · wcoup 12.299 · spec 2.803 · variant_rct
5. 2018 · PROTOCOL: Effects of lifestyle modification interventions to prevent and manage child and adolescent obesity: a systematic review · cited 3 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
6. 2014 · Placement and promotion strategies to increase sales of healthier products in supermarkets in low-income, ethnically diverse neighborhoods: a randomized controlled trial · cited 177 · queries 3 · inset 9 · wcoup 12.723 · spec 5.722 · generated
7. 2018 · Getting the balance right—tackling the obesogenic environment by reducing unhealthy options in a hospital shop without affecting profit · cited 13 · queries 6 · inset 1 · wcoup 0 · spec 0.734 · semantic
8. 2011 · Regulating Food Retail for Obesity Prevention: How Far Can Cities Go? · cited 16 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic
9. 2000 · Changes in supermarket sales during and after a staged health promotion campaign · cited 11 · queries 5 · inset 1 · wcoup 1.585 · spec 1.513 · semantic
10. 2013 · Overweight and obesity: Can we reconcile evidence about supermarkets and fast food retailers for public health policy? · cited 26 · queries 4 · inset 1 · wcoup 9.093 · spec 2.57 · semantic
11. 2021 · Retail Strategies to Support Healthy Eating · cited 1 · queries 0 · inset 0 · wcoup 23.677 · spec 10.563 · snowball_forward
12. 2016 · The impact of a pricing and communications intervention on stocking and sales of healthier foods in small Baltimore City food stores · cited 0 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
13. 2014 · Buying Food on Sale: A Mixed Methods Study With Shoppers at an Urban Supermarket, Philadelphia, Pennsylvania, 2010–2012 · cited 19 · queries 4 · inset 1 · wcoup 7.401 · spec 2.051 · semantic
14. 2016 · The year in cardiology 2016: prevention · cited 1 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
15. 2019 · Sustainable livestock systems to improve human health, nutrition, and economic status · cited 103 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct

## Top 15 under `mix_c`

1. 2016 · What is the effectiveness of obesity related interventions at retail grocery stores and supermarkets? —a systematic review · cited 199 · queries 7 · inset 7 · wcoup 25.455 · spec 7.327 · variant_sr
2. 2006 · Supermarkets, Other Food Stores, and Obesity · cited 1033 · queries 0 · inset 16 · wcoup 0.0 · spec 5.301 · snowball_backward
3. 2020 · The healthy food marketing strategies study: design, baseline characteristics, and supermarket compliance. · cited 9 · queries 7 · inset 0 · wcoup 18.045 · spec 4.692 · generated
4. 2019 · Environmental interventions to reduce the consumption of sugar-sweetened beverages and their effects on health · cited 304 · queries 6 · inset 1 · wcoup 12.299 · spec 2.803 · variant_rct
5. 2007 · Creating Healthy Food and Eating Environments: Policy and Environmental Approaches · cited 2364 · queries 0 · inset 13 · wcoup 0.0 · spec 3.851 · snowball_backward
6. 2020 · Retail Nutrition Programs and Outcomes: An Evidence Analysis Center Scoping Review · cited 17 · queries 0 · inset 0 · wcoup 29.884 · spec 8.384 · snowball_forward
7. 2019 · A Systematic Review of the Effect of Retail Food Environment Interventions on Diet and Health with a Focus on the Enabling Role of Public Policies · cited 132 · queries 0 · inset 3 · wcoup 38.169 · spec 8.363 · snowball_forward
8. 2012 · Retail Grocery Store Marketing Strategies and Obesity · cited 333 · queries 1 · inset 12 · wcoup 3.0 · spec 5.522 · semantic
9. 2025 · Health promotion through in-store communication: a systematic literature review of real environment experiments · cited 0 · queries 0 · inset 0 · wcoup 28.076 · spec 16.0 · snowball_forward
10. 2018 · PROTOCOL: Effects of lifestyle modification interventions to prevent and manage child and adolescent obesity: a systematic review · cited 3 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
11. 2009 · Effects of price discounts and tailored nutrition education on supermarket purchases: a randomized controlled trial · cited 270 · queries 0 · inset 12 · wcoup 0.0 · spec 4.904 · snowball_backward
12. 2021 · Point‐of‐sale nutrition information interventions in food retail stores to promote healthier food purchase and intake: A systematic review · cited 33 · queries 1 · inset 0 · wcoup 21.922 · spec 4.898 · semantic
13. 2016 · A Systematic Review of the Effectiveness of Supermarket-Based Interventions Involving Product, Promotion, or Place on the Healthiness of Consumer Purchases · cited 147 · queries 1 · inset 6 · wcoup 24.215 · spec 6.831 · semantic
14. 2013 · Supermarket and Grocery Store–Based Interventions to Promote Healthful Food Choices and Eating Practices: A Systematic Review · cited 223 · queries 1 · inset 12 · wcoup 12.755 · spec 7.181 · semantic
15. 2021 · Retail Strategies to Support Healthy Eating · cited 1 · queries 0 · inset 0 · wcoup 23.677 · spec 10.563 · snowball_forward

## Top 15 under `mix_q`

1. 2016 · What is the effectiveness of obesity related interventions at retail grocery stores and supermarkets? —a systematic review · cited 199 · queries 7 · inset 7 · wcoup 25.455 · spec 7.327 · variant_sr
2. 2006 · Supermarkets, Other Food Stores, and Obesity · cited 1033 · queries 0 · inset 16 · wcoup 0.0 · spec 5.301 · snowball_backward
3. 2020 · The healthy food marketing strategies study: design, baseline characteristics, and supermarket compliance. · cited 9 · queries 7 · inset 0 · wcoup 18.045 · spec 4.692 · generated
4. 2018 · PROTOCOL: Effects of lifestyle modification interventions to prevent and manage child and adolescent obesity: a systematic review · cited 3 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
5. 2007 · Creating Healthy Food and Eating Environments: Policy and Environmental Approaches · cited 2364 · queries 0 · inset 13 · wcoup 0.0 · spec 3.851 · snowball_backward
6. 2026 · P098 Investigation of the public’s drivers of food shopping choices and perspectives on the healthiness of supermarkets in England · cited 0 · queries 5 · inset 0 · wcoup 0 · spec 0.0 · generated
7. 2019 · Environmental interventions to reduce the consumption of sugar-sweetened beverages and their effects on health · cited 304 · queries 6 · inset 1 · wcoup 12.299 · spec 2.803 · variant_rct
8. 2012 · Retail Grocery Store Marketing Strategies and Obesity · cited 333 · queries 1 · inset 12 · wcoup 3.0 · spec 5.522 · semantic
9. 2020 · Effects of food policy actions on Indigenous Peoples’ nutrition-related outcomes: a systematic review · cited 73 · queries 4 · inset 0 · wcoup 4.392 · spec 1.042 · variant_sr
10. 2011 · Regulating Food Retail for Obesity Prevention: How Far Can Cities Go? · cited 16 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic
11. 2009 · Effects of price discounts and tailored nutrition education on supermarket purchases: a randomized controlled trial · cited 270 · queries 0 · inset 12 · wcoup 0.0 · spec 4.904 · snowball_backward
12. 2025 · Obesity plan puts onus on supermarkets to promote healthy food · cited 6 · queries 4 · inset 0 · wcoup 0 · spec 0.0 · semantic
13. 2018 · Getting the balance right—tackling the obesogenic environment by reducing unhealthy options in a hospital shop without affecting profit · cited 13 · queries 6 · inset 1 · wcoup 0 · spec 0.734 · semantic
14. 2013 · Supermarket and Grocery Store–Based Interventions to Promote Healthful Food Choices and Eating Practices: A Systematic Review · cited 223 · queries 1 · inset 12 · wcoup 12.755 · spec 7.181 · semantic
15. 2026 · Retail Marketing Strategies, Purchasing, and Prices: A Scoping Review to Inform Healthy Food Targets · cited 0 · queries 4 · inset 0 · wcoup 0 · spec 0.0 · generated

## Top 15 under `mix_f1`

1. 2016 · What is the effectiveness of obesity related interventions at retail grocery stores and supermarkets? —a systematic review · cited 199 · queries 7 · inset 7 · wcoup 25.455 · spec 7.327 · variant_sr
2. 2006 · Supermarkets, Other Food Stores, and Obesity · cited 1033 · queries 0 · inset 16 · wcoup 0.0 · spec 5.301 · snowball_backward
3. 2020 · The healthy food marketing strategies study: design, baseline characteristics, and supermarket compliance. · cited 9 · queries 7 · inset 0 · wcoup 18.045 · spec 4.692 · generated
4. 2019 · Environmental interventions to reduce the consumption of sugar-sweetened beverages and their effects on health · cited 304 · queries 6 · inset 1 · wcoup 12.299 · spec 2.803 · variant_rct
5. 2007 · Creating Healthy Food and Eating Environments: Policy and Environmental Approaches · cited 2364 · queries 0 · inset 13 · wcoup 0.0 · spec 3.851 · snowball_backward
6. 2026 · P098 Investigation of the public’s drivers of food shopping choices and perspectives on the healthiness of supermarkets in England · cited 0 · queries 5 · inset 0 · wcoup 0 · spec 0.0 · generated
7. 2018 · PROTOCOL: Effects of lifestyle modification interventions to prevent and manage child and adolescent obesity: a systematic review · cited 3 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
8. 2012 · Retail Grocery Store Marketing Strategies and Obesity · cited 333 · queries 1 · inset 12 · wcoup 3.0 · spec 5.522 · semantic
9. 2020 · Effects of food policy actions on Indigenous Peoples’ nutrition-related outcomes: a systematic review · cited 73 · queries 4 · inset 0 · wcoup 4.392 · spec 1.042 · variant_sr
10. 2011 · Regulating Food Retail for Obesity Prevention: How Far Can Cities Go? · cited 16 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic
11. 2009 · Effects of price discounts and tailored nutrition education on supermarket purchases: a randomized controlled trial · cited 270 · queries 0 · inset 12 · wcoup 0.0 · spec 4.904 · snowball_backward
12. 2025 · Obesity plan puts onus on supermarkets to promote healthy food · cited 6 · queries 4 · inset 0 · wcoup 0 · spec 0.0 · semantic
13. 2018 · Getting the balance right—tackling the obesogenic environment by reducing unhealthy options in a hospital shop without affecting profit · cited 13 · queries 6 · inset 1 · wcoup 0 · spec 0.734 · semantic
14. 2013 · Supermarket and Grocery Store–Based Interventions to Promote Healthful Food Choices and Eating Practices: A Systematic Review · cited 223 · queries 1 · inset 12 · wcoup 12.755 · spec 7.181 · semantic
15. 2026 · Retail Marketing Strategies, Purchasing, and Prices: A Scoping Review to Inform Healthy Food Targets · cited 0 · queries 4 · inset 0 · wcoup 0 · spec 0.0 · generated

## Top 15 under `mix`

1. 2016 · What is the effectiveness of obesity related interventions at retail grocery stores and supermarkets? —a systematic review · cited 199 · queries 7 · inset 7 · wcoup 25.455 · spec 7.327 · variant_sr
2. 2006 · Supermarkets, Other Food Stores, and Obesity · cited 1033 · queries 0 · inset 16 · wcoup 0.0 · spec 5.301 · snowball_backward
3. 2020 · The healthy food marketing strategies study: design, baseline characteristics, and supermarket compliance. · cited 9 · queries 7 · inset 0 · wcoup 18.045 · spec 4.692 · generated
4. 2019 · Environmental interventions to reduce the consumption of sugar-sweetened beverages and their effects on health · cited 304 · queries 6 · inset 1 · wcoup 12.299 · spec 2.803 · variant_rct
5. 2007 · Creating Healthy Food and Eating Environments: Policy and Environmental Approaches · cited 2364 · queries 0 · inset 13 · wcoup 0.0 · spec 3.851 · snowball_backward
6. 2020 · Effects of food policy actions on Indigenous Peoples’ nutrition-related outcomes: a systematic review · cited 73 · queries 4 · inset 0 · wcoup 4.392 · spec 1.042 · variant_sr
7. 2018 · PROTOCOL: Effects of lifestyle modification interventions to prevent and manage child and adolescent obesity: a systematic review · cited 3 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · variant_rct
8. 2012 · Retail Grocery Store Marketing Strategies and Obesity · cited 333 · queries 1 · inset 12 · wcoup 3.0 · spec 5.522 · semantic
9. 2026 · P098 Investigation of the public’s drivers of food shopping choices and perspectives on the healthiness of supermarkets in England · cited 0 · queries 5 · inset 0 · wcoup 0 · spec 0.0 · generated
10. 2011 · Regulating Food Retail for Obesity Prevention: How Far Can Cities Go? · cited 16 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic
11. 2009 · Effects of price discounts and tailored nutrition education on supermarket purchases: a randomized controlled trial · cited 270 · queries 0 · inset 12 · wcoup 0.0 · spec 4.904 · snowball_backward
12. 2022 · Food Sales and Adult Weight Status: Results of a Cross-Sectional Study in England · cited 2 · queries 4 · inset 0 · wcoup 7.129 · spec 2.78 · semantic
13. 2018 · Getting the balance right—tackling the obesogenic environment by reducing unhealthy options in a hospital shop without affecting profit · cited 13 · queries 6 · inset 1 · wcoup 0 · spec 0.734 · semantic
14. 2013 · Supermarket and Grocery Store–Based Interventions to Promote Healthful Food Choices and Eating Practices: A Systematic Review · cited 223 · queries 1 · inset 12 · wcoup 12.755 · spec 7.181 · semantic
15. 2021 · Point‐of‐sale nutrition information interventions in food retail stores to promote healthier food purchase and intake: A systematic review · cited 33 · queries 1 · inset 0 · wcoup 21.922 · spec 4.898 · semantic
