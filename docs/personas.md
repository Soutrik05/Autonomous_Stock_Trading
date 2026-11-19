# StockMinds — Persona & Strategy Philosophies

> **Document Purpose:** This document maintains a comprehensive, non-codified reference for each trading and investing persona in the StockMinds arena. It records the real-world inspiration, theoretical foundations, implementation architecture, metrics, constraints, and research hypotheses. It is maintained incrementally as each agent undergoes review and refinement.

---

## Master Cross-Persona Comparison Matrix

> **The Decoupling Principle:** In this architecture, **`ttl_days`** (Stage-3 watchlist lock) governs *how fast an entry setup decays* without execution, while **Holding Horizon** and **`eval_horizon_days`** govern *how long an eventual position runs and when its thesis can be evaluated*. These clocks are decoupled: an agent buying sharp technical oversold dips (e.g. Marks) requires a short TTL (10d) to prevent stale candidates from trapping watchlist capacity, even though its recovery trade may take up to 120 days.

### One-Look Persona Comparison: Characteristics & Timeframes

| Persona & Agent ID | Strategy School & Philosophy | Target Holding Horizon | Watchlist TTL (`ttl_days`) | Prompt Lookback (`lookback_days`) | Thesis Eval Horizon (`eval_horizon_days`) | Exemplar Win Hold (`min_win_hold_days`) | Portfolio Capacity & Position Cap | Target Risk Budget (`target_risk_pct`) | Stop Loss Floor (`atr_stop_multiplier`) | Long-Term Trend Filter (`require_above_ema200`) | Fundamental History (`fundamentals_depth`) | News Lookback (`news_lookback_days`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Jimmy**<br>(`simons`) | **Quantitative Momentum & Statistical Edge**<br>Orthogonal multi-factor confluence; mathematical factor efficiency; zero fundamental or narrative bias. | **1–14 d**<br>(stagnant time-stop @ 8d) | **3 d** | **14 d** | **5 d** | $\ge +4.0\%$ in $\ge$ **1 d** | 12 open positions<br>(10.0% max cap, sector cap 3) | **0.75%**<br>(volatility parity) | $\ge 1.5\times\text{ATR-14}$ | **True**<br>(strictly above 200 EMA) | `none`<br>(0 quarters) | `0 d`<br>(zero exposure) |
| **StockMinds Core**<br>(`varsity`) | **Balanced Hybrid & DCF Intrinsic Value**<br>Zerodha Varsity Module 1 & 9 principles; dual confluence of technical timing and margin of safety. | **20–75 d**<br>(swing-to-position) | **14 d**<br>(DCF cadence) | **90 d** | **20 d** | $\ge +5.0\%$ in $\ge$ **10 d** | 10 open positions<br>(10.0% max cap, sector cap 2) | **1.00%**<br>(Half-Kelly calibrated) | $\ge 2.0\times\text{ATR-14}$ | **True**<br>(strictly above 200 EMA) | `8q`<br>(8 quarters) | `7 d`<br>(catalyst validation) |
| **Howard Marks**<br>(`marks`) | **Contrarian Deep Value & Margin of Safety**<br>Second-level thinking; buying cyclical despair with sound balance sheets; separating panic from fatal value traps. | **21–120 d**<br>(cyclical recovery) | **10 d**<br>(dip decay) | **90 d** | **60 d** | $\ge +6.0\%$ in $\ge$ **14 d** | 8 open positions<br>(12.5% max cap, sector cap 2) | **1.25%**<br>(asymmetric recovery) | $\ge 2.5\times\text{ATR-14}$ | **False**<br>(can buy oversold below 200 EMA) | `3y`<br>(3 years) | `14 d`<br>(solvency / crisis check) |
| **Peter Lynch**<br>(`lynch`) | **GARP & PEG-Anchored Business Compounders**<br>Growth at a reasonable price; cash-flow validation (CFO/PAT $\ge 0.8$); category classification; earnings momentum. | **30–90 d**<br>(quarterly cadence) | **14 d** | **120 d** | **60 d** | $\ge +10.0\%$ in $\ge$ **15 d** | 5 open positions<br>(20.0% max cap, sector cap 2) | **1.50%**<br>(conviction sizing) | $\ge 2.5\times\text{ATR-14}$ | **False**<br>(can buy cyclicals / turnarounds) | `4y`<br>(4 audited annuals) | `30 d`<br>(operational execution) |
| **Rakesh Jhunjhunwala**<br>(`jhunjhunwala`) | **High-Conviction Growth & India Megatrends**<br>Promoter quality; institutional sponsorship footprint; secular domestic tailwinds; pyramiding into winners. | **90–180 d**<br>(secular compounding) | **14 d** | **150 d** | **90 d** | $\ge +15.0\%$ in $\ge$ **45 d** | 6 open positions<br>(20.0% max cap + Pyramiding) | **1.50%**<br>(high-conviction book) | $\ge 3.5\times\text{ATR-14}$ | **True**<br>(strictly above 200 EMA) | `12q`<br>(12 quarters) | `21 d`<br>(capex, PLI, infra orders) |

---

## Agent 1: Jimmy (Quantitative-Statistical Trader) & Baseline-Jimmy

| Attribute | Specification |
| :--- | :--- |
| **Agent ID (Database)** | `simons` (LLM Agent: Display Name "Jimmy") |
| **Baseline ID (Database)** | `baseline-simons-rules` (Pure Python Rules Agent) |
| **Strategy School** | Quantitative Momentum & Statistical Drift |
| **Account Capital** | ₹1,00,000 Paper Equity (separate account per agent) |
| **Holding Horizon** | Short swing: 1–14 trading sessions (`ttl_days = 3`, `lookback_days = 14`, `eval_horizon_days = 5`) |
| **Portfolio Capacity** | Up to 12 concurrent open positions (diversified book) |
| **Position Cap** | Maximum 10.0% of portfolio equity per ticker |
| **Target Risk Budget** | 0.75% capital risk per trade (volatility parity) |
| **Stop Loss Floor** | Minimum distance $\ge 1.5 \times \text{ATR-14}$ below entry price |
| **Target Price Range** | Adaptive reference band: $\approx \text{entry\_high} + (2.5\text{ to } 3.5) \times \text{ATR-14}$ ($1 : 1.7\text{ to } 1 : 2.3$ Risk-to-Reward) |
| **Sector Cap** | Maximum 3 candidates / positions per industry sector (`sector_cap = 3`, up to 30% concentration) |
| **News / Narrative Exposure** | Zero (`news_lookback_days = 0`) |
| **Fundamentals Exposure** | Zero (`fundamentals_depth = "none"`) |

---

### 1. Real-World Inspiration: Jim Simons & Renaissance Technologies

#### The Person & The Institution
Jim Simons was an award-winning mathematician, former Cold War cryptanalyst at the Institute for Defense Analyses (IDA), co-inventor of the Chern-Simons form in differential geometry, and the founder of Renaissance Technologies (RenTech). Its flagship Medallion Fund is widely considered the most successful quantitative investment vehicle in financial history, generating estimated annualized net returns exceeding 35–40% over three decades.

#### Real-World Core Philosophy
1. **The Anti-Story Doctrine:** Simons fundamentally rejected human narratives, economic forecasts, and intuitive opinions. RenTech's models did not attempt to understand "why" an anomaly existed; they looked for subtle, non-random, mathematically measurable statistical anomalies that reliably recurred in market noise.
2. **The Law of Large Numbers:** Medallion’s statistical edge on any single trade was razor-thin—estimated between 50.75% and 51.5% win rate. The fund made millions by scaling this slight edge across thousands of uncorrelated bets with strict risk control:
   $$\text{Information Ratio} \approx \text{Information Coefficient} \times \sqrt{\text{Breadth}}$$
3. **Volatility Parity & Position Sizing:** Capital was never allocated based on subjective "conviction." Position sizing was strictly proportional to predicted return and inversely proportional to asset and portfolio volatility.
4. **Alpha Decay & Time-Stops:** In quantitative momentum and statistical arbitrage, alpha has a measurable half-life. If an expected price drift does not materialize within the modeled time window, the edge has decayed into random noise, and the trade is closed regardless of profit or loss.
5. **Absence of Retail Chartism:** Simons sneered at classical retail technical analysis (trendlines, head-and-shoulders, cup-and-handle). RenTech operated on time series properties, autocorrelation, covariance matrices, and microstructure dynamics.

---

### 2. The Essence We Capture in Jimmy

Because our system operates on daily candles on the Nifty 500 cash equity market without leverage or short selling, we do not claim to replicate Renaissance Technologies. Instead, Jimmy simulates an **autonomous quantitative-statistical momentum desk** adhering to the mathematical principles of systematic factor investing:

1. **Zero Fundamental & Narrative Bias:** Jimmy is completely insulated from quarterly reports, PE ratios, management interviews, and news headlines. If it cannot be derived from price, volume, and volatility time series, it does not exist for this agent.
2. **Multi-Factor Confluence (Orthogonal Filters):** Rather than relying on a single indicator, Jimmy requires independent statistical confirmation across five distinct dimensions:
   - *Trend Alignment:* Intermediate and long-term trend anchors (`ema_20_above_50`, price above 20 EMA and 200 EMA).
   - *Trend Directional Strength:* Directional index (`adx_14 >= 22.0`).
   - *Trajectory Efficiency (Noise Filter):* Kaufman Efficiency Ratio (`kaufman_er_20 >= 0.30`) to reject erratic, Brownian chop.
   - *Momentum Window:* Controlled acceleration without overbought exhaustion (`rsi_14 in [52, 72]`, `macd_hist > 0`).
   - *Volume Accumulation Flow:* Volume expansion (`volume_surge >= 1.2`) confirmed by non-negative On-Balance Volume slope (`obv_slope_sign >= 0`).
3. **Cross-Sectional Percentile Rank Composite:** Candidates are ranked using a unitless multi-factor composite percentile:
   $$\text{intensity\_score} = \left(\frac{R_{\text{vol}} + R_{\text{ker}} + R_{\text{adx}}}{3}\right) \times (0.8 \text{ if } \text{obv\_slope} < 0 \text{ else } 1.0)$$
4. **First-Principles Volatility Parity Sizing:** Sizing is derived mathematically from candidate volatility (ATR-14) and the risk budget:
   $$\text{shares} \approx \left\lfloor \frac{\text{account\_value} \times 0.0075}{\text{entry\_high} - \text{stop\_loss\_price}} \right\rfloor$$
5. **Systematic Time-Stop (Alpha Decay):** If an open position fails to achieve at least $1.0 \times \text{ATR-14}$ favorable move within 8 trading sessions, or if its Kaufman Efficiency collapses ($< 0.20$), the edge is deemed expired, and a `SELL` is triggered to reallocate capital.
6. **Capital Preservation:** An absolute conviction floor ($0.55$) and a 5% uncommitted liquid cash reserve floor ensure the agent holds cash in deteriorating markets.

---

### 3. Real World vs. Our Implementation: Gaps & Constraints

| Dimension | Real-World RenTech / Quant Fund | StockMinds Implementation (Jimmy) | Impact & Rationale |
| :--- | :--- | :--- | :--- |
| **Trading Universe** | Thousands of global assets (equities, futures, FX, commodities, options). | Nifty 500 constituents (Indian cash equity). | Limited breadth ($N=500$), bounded by exchange constituent list. |
| **Directionality** | Long / Short market-neutral pairs and factor books. | Long-only delivery (cash segment). | Hard regulatory constraint: Indian equity delivery does not permit overnight short selling without borrowing. |
| **Execution Frequency** | Millisecond / Tick / Intraday order book microstructure. | Daily end-of-day candles; 10-minute poll execution. | Operates on daily swing anomalies rather than high-frequency statistical arbitrage. |
| **Leverage** | 5x to 20x gross exposure. | 1.0x cash (₹1,00,000 unmargined paper cash). | Risk is constrained to absolute equity; drawdown cannot trigger margin liquidation. |
| **Model Nature** | Non-linear stochastic differential equations, hidden Markov models, kernel density estimators. | **Dual Testing Harness:**<br>• LLM Agent: Pattern recognition across numeric feature snapshots.<br>• Rules Agent: Deterministic Python closed-form if-else math. | Tests whether an LLM decision layer adds measurable value over deterministic rules on identical data. |

---

### 4. Metrics & Features Used

| Feature Name | Category | Mathematical Definition | Role in Persona | Match Tolerance |
| :--- | :--- | :--- | :--- | :--- |
| `close` | Price | Daily EOD close in ₹ | Execution reference & level anchor | `REL(0.5%)` |
| `ema_20`, `ema_50`, `ema_200` | Trend | Exponential moving averages (20, 50, 200) | Identifies multi-horizon trend structure | `REL(0.5%)` |
| `ema_20_above_50` | Trend | Boolean flag ($EMA_{20} > EMA_{50}$) | Hard gate: intermediate trend alignment | `EXACT` |
| `rsi_14` | Momentum | Wilder 14-period RSI $[0, 100]$ | Entry sweet spot ($52\text{--}72$); filters exhaustion | `ABS(2.0)` |
| `macd_hist` | Momentum | $(EMA_{12} - EMA_{26}) - EMA_9$ | Confirms positive price momentum acceleration | `ABS_PCT_CLOSE(0.1)` |
| `adx_14` | Momentum | Wilder 14-period Average Directional Index | Trend strength hurdle ($\ge 22.0$) | `ABS(2.0)` |
| `atr_14` | Volatility | Wilder 14-period Average True Range | Volatility stop floor ($1.5\times$) & share sizing | `REL(5.0%)` |
| `volume_surge` | Volume | $V_t / \text{SMA}_{20}(V)$ | Volume breakout confirmation ($\ge 1.2\times$) | `REL(5.0%)` |
| `obv_slope_sign` | Volume | 10-session linear regression slope sign $\{-1, 0, 1\}$ | Verifies volume is accumulating, not distributing | `EXACT` |
| `kaufman_er_20` | Structure | $\frac{\|C_t - C_{t-20}\|}{\sum_{i=0}^{19} \|C_{t-i} - C_{t-i-1}\|}$ | Trend efficiency $[0, 1]$; filters out choppy noise | `ABS(0.05)` |
| `zscore_close_20` | Structure | $(C_t - \mu_{20}) / \sigma_{20}$ | Identifies statistical deviation from 20-day mean | `ABS(0.2)` |
| `parkinson_vol_ratio`| Volatility | $\sqrt{\frac{1}{4 \ln 2 \cdot N} \sum \ln(H_t/L_t)^2} \times 100$ | High-Low extreme value volatility percentage | `REL(5.0%)` |
| `skew_60` | Structure | 60-day rolling sample return skewness | Directional asymmetry: warns of left-tail crash risk | `ABS(0.1)` |

---

### 5. Paired Scientific Comparison: LLM vs. Rules Baseline

To answer the core research question (*"Does an LLM decision layer add demonstrable value over a rules-only baseline?"*), Jimmy and `baseline-simons-rules` operate under strict scientific parity:

```
                            NIFTY 500 UNIVERSE
                                    │
                    STAGE 0: Liquidity & Turnover Gate
                                    │
                    STAGE 1: Jimmy Technical Hurdles
                                    │
                    STAGE 2: Percentile Rank Composite Sort
                                    │
                    STAGE 3: Sector Cap (3) & TTL Lock (3d)
                                    │
                       IDENTICAL 20-CANDIDATE POOL
                                    │
         ┌──────────────────────────┴──────────────────────────┐
         ▼                                                     ▼
┌─────────────────────────────────┐   ┌────────────────────────────────┐
│ Jimmy (LLM Quant Agent)         │   │ baseline-simons-rules (Python) │
│ • Evaluates numeric snapshots   │   │ • Pure closed-form if-else     │
│ • Adaptive trade triage         │   │ • Conviction floor: score>=0.55│
│ • Contextual risk allocation    │   │ • 5% uncommitted cash reserve  │
│ • Pre-mortem failure deduction  │   │ • Volatility parity sizing     │
└────────────────┬────────────────┘   └────────────────┬───────────────┘
                 │                                     │
                 └──────────────────┬──────────────────┘
                                    ▼
                         PAPER BROKER EXECUTION
                 (Same slippage, same charges, same stops)
```

#### Three-State BUY Tracking & Sizing Fidelity
For every BUY generated by the LLM, the system tracks three states:
1. **Raw LLM Decision (`raw_llm_json`):** Exactly what the model output prior to any broker safety nets.
2. **Placed Execution:** What was submitted to the broker after clamping to safety boundaries (cash, price logic).
3. **Formulaic Shadow Counterfactual:** What pure mathematical volatility parity would have calculated for that exact same stock pick.
4. **Sizing Fidelity Score:** Measures the arithmetic precision of the LLM:
   $$\text{sizing\_fidelity\_score} = 1.0 - \min\left(1.0, \frac{|\text{actual\_shares} - \text{counterfactual\_shares}|}{\text{counterfactual\_shares}}\right)$$

---

### 6. Research Hypotheses & What We Expect to Find

1. **Selection Alpha vs. Sizing Drag:** Does the LLM make superior stock selections among qualifying candidates (e.g., catching false breakouts via cross-metric tension between ADX and KER), but suffer from arithmetic drag in sizing calculations compared to the rules baseline?
2. **Pre-Mortem Predictive Validity:** Does the LLM’s mandatory `pre_mortem_risk` clause correlate with actual post-mortem forensic classifications when positions are closed at a loss?
3. **Faithfulness & Hallucination Rate:** Given dense numeric candidate rows, what fraction of cited metrics in Jimmy's decisions match the underlying `FeatureSnapshot` within defined tolerances?
4. **Market Regime Resilience:** In choppy or sideways regimes (India VIX $> 18$ or declining breadth), does the LLM correctly exercise discipline and output `HOLD`, or does it suffer from a bias toward action compared to the baseline's rigid conviction floor?

---

## Agent 2: Peter Lynch (Growth at a Reasonable Price — GARP)

| Attribute | Specification |
| :--- | :--- |
| **Agent ID (Database)** | `lynch` (LLM Agent: Display Name "Peter Lynch") |
| **Baseline Status** | LLM-only in MVP (Rules baseline reserved for post-MVP comparison) |
| **Strategy School** | Growth at a Reasonable Price (GARP) & Business Compounding |
| **Account Capital** | ₹1,00,000 Paper Equity (separate account) |
| **Holding Horizon** | Intermediate-to-long: 30–90 trading sessions (`ttl_days = 14`, `lookback_days = 120`, `eval_horizon_days = 60`) |
| **Portfolio Capacity** | Up to 5 concurrent open positions (concentrated book) |
| **Position Cap** | Maximum 20.0% of portfolio equity per ticker |
| **Target Risk Budget** | 1.50% capital risk per trade |
| **Stop Loss Floor** | Minimum distance $\ge 2.5 \times \text{ATR-14}$ below entry price |
| **Target Price Range** | Minimum $1 : 2.0$ Risk-to-Reward ($\approx \text{entry\_high} + 4.0\text{--}6.0 \times \text{ATR-14}$) |
| **News / Narrative Exposure** | Operational execution and business health only (`news_lookback_days = 30`) |
| **Fundamentals Exposure** | 4 fiscal years of audited statements & ratios (`fundamentals_depth = "4y"`)* |

> [!NOTE] Upstox Ingestion Ground Truth on 4 Fiscal Years of Data Depth
> Upstox V2 API endpoints (`/v2/fundamentals/{isin}/income-statement?type=consolidated&time_period=yearly&fs=true`) provide 4 trailing annual audited statements (`Mar 2023`, `Mar 2024`, `Mar 2025`, `Mar 2026`). For Peter Lynch's framework, 4 fiscal years (48 months) of audited financials is significantly superior to 8 quarters (24 months): it eliminates quarterly seasonal noise (e.g. festival/monsoon cyclicality in Indian equities) and captures complete multi-year compounding cycles for robust categorization into Fast Growers, Stalwarts, Cyclicals, and Turnarounds. Hence, `fundamentals_depth` is calibrated to `"4y"`.

---

### 1. Real-World Inspiration: Peter Lynch & Fidelity Magellan Fund

#### The Person & The Track Record
Peter Lynch managed Fidelity's Magellan Fund from 1977 to 1990. Under his stewardship, Magellan's assets grew from $18 million to $14 billion, achieving an annualized compound return of 29.2%—outperforming the S&P 500 in 11 of his 13 years and making it the top-performing mutual fund in the world. He authored seminal investment texts: *One Up on Wall Street* (1989), *Beating the Street* (1993), and *Learn to Earn* (1995).

#### Real-World Core Philosophy
1. **The PEG Ratio (Valuation Anchored to Growth):** Lynch popularized the Price/Earnings-to-Growth (PEG) ratio:
   $$\text{PEG} = \frac{\text{P/E}}{\text{Annual EPS Growth Rate (\%)}}$$
   - $\text{PEG} \approx 1.0$: Fairly valued.
   - $\text{PEG} < 0.5$: A potential bargain ("buying growth at a discount").
   - $\text{PEG} > 1.5\text{--}2.0$: Growth is fully priced in; vulnerable to multiple contraction if growth falters.
2. **"Know What You Own":** Lynch insisted that investors must understand a company’s basic business model, products, and competitive positioning before putting money to work. Complex financial engineering and incomprehensible business models were avoided.
3. **The Power of the Ten-Bagger:** Rather than looking for small, incremental trading edges, Lynch sought businesses capable of multiplying capital several-fold. In a concentrated portfolio, a single ten-bagger can drive portfolio outperformance even if several other investments produce mediocre results:
   $$\text{Downside is capped at } 100\%; \text{ upside is open-ended } (1000\%+)$$
4. **Categorization of Companies:** Lynch classified equities into six distinct archetypes:
   - *Fast Growers:* Small-to-mid companies compounding earnings at $20\%\text{--}25\%$ annually in expanding niches.
   - *Stalwarts:* Large, steady compounders ($10\%\text{--}15\%$ earnings growth), reliable during economic downturns.
   - *Cyclicals:* Companies whose fortunes rise and fall with macroeconomic cycles (timing is paramount).
   - *Turnarounds:* Depressed companies restructuring or recovering from bankruptcy risk.
   - *Asset Plays:* Companies possessing hidden or undervalued assets (real estate, patents, natural resources).
   - *Slow Growers:* Mature companies paying high dividends but offering limited capital appreciation.
5. **Operational Health over Macro Forecasts:** Lynch famously quipped: *"If you spend 13 minutes a year on economics, you’ve wasted 10 minutes."* He paid zero attention to interest rate forecasts or GDP predictions, focusing entirely on grassroots operational evidence: store rollouts, factory capacity utilization, order books, and cash generation.
6. **Balance Sheet Resilience:** *"It’s tough to go out of business if you don’t own anybody any money."* Companies with negligible long-term debt and strong net cash were strongly favored.

---

### 2. The Essence We Capture in Peter Lynch

In StockMinds, Peter Lynch is implemented as an **autonomous fundamental GARP investor** tailored for intermediate swing compounding on the Nifty 500:

1. **Fundamental Hurdle Filter (Stage 1):** Unlike Jimmy's pure price-volume gate, Lynch applies a multi-factor solvency, valuation, and earnings quality screen:
   - $\text{PEG} < 1.0$: Non-negotiable valuation safety buffer.
   - $\text{ROCE} > 15.0\%$: High return on capital employed confirms moat and self-funding capacity.
   - $\text{D/E} < 0.8$: Low debt-to-equity protects against solvency hazards.
   - $\text{CFO} / \text{PAT} > 0.8$: Operating cash flows must substantiate reported accounting profits.
   - $\text{PAT Growth YoY} \ge 8.0\%$: Positive earnings growth floor.
2. **Multi-Factor GARP Percentile Composite (Stage 2):** Candidates are ranked cross-sectionally across three orthogonal fundamental dimensions:
   - $R_{\text{peg}}$: Cross-sectional percentile rank of $1 / \max(0.01, \text{PEG})$ (cheaper growth ranks higher).
   - $R_{\text{roce}}$: Cross-sectional percentile rank of $\text{ROCE}$.
   - $R_{\text{cfo}}$: Cross-sectional percentile rank of $\text{CFO} / \text{PAT}$.
   - Composite Intensity Score:
     $$\text{intensity\_score} = \min\left(1.0, \; \left(\frac{R_{\text{peg}} + R_{\text{roce}} + R_{\text{cfo}}}{3}\right) \times (1.10 \text{ if } \text{pat\_growth\_yoy} \ge 15.0\% \text{ else } 1.0)\right)$$
3. **Concentrated 5-Stock Portfolio:** Reflecting Lynch's guidance for individual investors in *One Up on Wall Street*, Lynch holds up to 5 concurrent positions with a maximum 20% equity cap per ticker.
4. **Volatility Breathing Room ($2.5\times \text{ATR-14}$):** Because fundamental re-rating requires quarterly earnings cycles to unfold, stops are placed at least $2.5\times \text{ATR-14}$ below entry low to prevent premature shakeouts from normal daily noise.
5. **Operational Catalyst Guidance:** The prompt directs the agent to evaluate corporate developments (expansions, product launches, operational margins) while filtering out macroeconomic headlines and media sentiment buzz.
6. **Story Degradation Exits:** The agent evaluates open holdings against story integrity: if PEG expands past 1.5x with decelerating growth, or if CFO/PAT drops below 0.6x, a `SELL` is triggered to reallocate capital.

---

### 3. Real World vs. Our Implementation: Gaps & Constraints

| Dimension | Real-World Peter Lynch (Magellan) | StockMinds Implementation (Peter Lynch) | Impact & Rationale |
| :--- | :--- | :--- | :--- |
| **Portfolio Breadth** | Up to 1,400 stocks at peak due to $14B asset size. | 5 concentrated positions (20% cap per position). | Faithful to Lynch's personal book advice for smaller accounts ($3\text{--}6$ stocks). |
| **Holding Period** | Months to several years (until the business thesis matures). | 30 to 90 trading days (`ttl_days = 14`, `lookback_days = 120`, `eval_horizon_days = 60`). | Calibrated for quarterly earnings swing cycles within the 8-week paper trading testbed. |
| **Grassroots Channel Checks** | Visiting stores, testing products, talking to store managers and customers. | Ingested corporate news headlines, press releases, and FinBERT sentiment. | LLM processes textual execution clues (e.g. "capacity addition", "order win") in lieu of physical store visits. |
| **Stop Loss Concept** | Lynch rarely used mechanical stop losses; he monitored the "story." | Volatility-aware stop floor ($\ge 2.5\times \text{ATR-14}$) enforced by the broker. | Necessary risk control in automated trading to prevent catastrophic downside on fraud or sudden crashes. |
| **Balance Sheet Restructuring** | Ability to analyze complex turnaround debt restructuring and covenants. | Standard standardized ratios ($\text{D/E}$, interest coverage, $\text{CFO}/\text{PAT}$). | Standardized financial data pipeline from Upstox fundamentals cache. |

---

### 4. Metrics & Features Used

| Feature Name | Category | Mathematical Definition | Role in Persona | Match Tolerance |
| :--- | :--- | :--- | :--- | :--- |
| `close` | Price | Daily EOD close in ₹ | Execution reference price | `REL(0.5%)` |
| `peg` | Valuation | $\text{P/E} / \text{PAT Growth YoY (\%)}$ | Primary valuation anchor ($< 1.0$) | `REL(5.0%)` |
| `pe` | Valuation | Price-to-Earnings Ratio | Historical and peer multiple context | `REL(5.0%)` |
| `roce_pct` | Quality | $\text{EBIT} / (\text{Total Assets} - \text{Current Liabilities}) \times 100$ | Return on capital employed hurdle ($> 15\%$) | `ABS(1.0)` |
| `roe_pct` | Quality | $\text{Net Income} / \text{Shareholders' Equity} \times 100$ | Return on equity verification ($> 15\%$) | `ABS(1.0)` |
| `debt_to_equity` | Solvency | $\text{Total Debt} / \text{Total Equity}$ | Leverage hurdle ($< 0.8$) | `ABS(0.05)` |
| `cfo_to_pat` | Cash Flow | $\text{Cash Flow from Operations} / \text{PAT}$ | Earnings quality & cash conversion ($> 0.8$) | `ABS(0.05)` |
| `pat_growth_yoy_pct` | Growth | YoY quarterly PAT growth percentage | Growth floor ($\ge 8\%$) and acceleration bonus | `ABS(1.0)` |
| `atr_14` | Volatility | Wilder 14-period Average True Range | Volatility breathing stop ($2.5\times$) | `REL(5.0%)` |
| `news_sentiment` | Catalyst | FinBERT headline sentiment score $[-1, 1]$ | Evaluates operational execution headlines | `ABS(0.05)` |
| `dist_52w_high_pct` | Structure | $(C_t - \text{High}_{52w}) / \text{High}_{52w} \times 100$ | Identifies drawdowns from annual highs | `ABS(1.0)` |
| `dist_52w_low_pct` | Structure | $(C_t - \text{Low}_{52w}) / \text{Low}_{52w} \times 100$ | Verifies recovery from annual lows | `ABS(1.0)` |

---

### 5. Research Hypotheses & What We Expect to Find

1. **Fundamental Story vs. Volatility Noise:** Does a wide $2.5\times \text{ATR}$ stop allow high-quality GARP compounders to survive market chop and generate larger winning trades compared to tight systematic stops?
2. **Textual News Extraction of Execution Clues:** Does the LLM effectively distinguish between operational progress headlines (e.g., plant commissioning, margin expansion) and transient market gossip when forming its investment reasoning?
3. **Valuation Multiple Discipline:** Does the LLM demonstrate discipline by rejecting candidates that pass numerical PEG hurdles if qualitative news indicates unsustainable one-off gains?
4. **Concentration Return Impact:** In a 5-stock concentrated portfolio with 20% sizing, do winning trades generate sufficient alpha to overcome the drag of longer holding durations in flat market regimes?

---

## Agent 3: Howard Marks (Contrarian Value & Distressed Quality)

| Attribute | Specification |
| :--- | :--- |
| **Agent ID (Database)** | `marks` (LLM Agent: Display Name "Howard Marks") |
| **Baseline Status** | LLM-only in MVP (Rules baseline reserved for post-MVP comparison) |
| **Strategy School** | Contrarian Deep Value & Asymmetric Risk Control |
| **Account Capital** | ₹1,00,000 Paper Equity (separate account) |
| **Holding Horizon** | Intermediate: 21–120 trading sessions (`ttl_days = 10`, `lookback_days = 90`, `eval_horizon_days = 60`) |
| **Portfolio Capacity** | Up to 8 concurrent open positions (diversified contrarian book) |
| **Position Cap** | Maximum 12.5% of portfolio equity per ticker |
| **Target Risk Budget** | 1.25% capital risk per trade |
| **Stop Loss Floor** | Minimum distance $\ge 2.5 \times \text{ATR-14}$ below entry price |
| **Target Price Range** | Minimum $1 : 2.0$ Risk-to-Reward ($\approx \text{entry\_high} + 4.0\text{--}6.0 \times \text{ATR-14}$) |
| **News / Narrative Exposure** | Forensic solvency vs fatal value traps (`news_lookback_days = 14`) |
| **Fundamentals Exposure** | 3 years of historical financial statements & ratios (`fundamentals_depth = "3y"`) |

---

### 1. Real-World Inspiration: Howard Marks & Oaktree Capital Management

#### The Person & The Institution
Howard Marks is the co-founder and co-chairman of Oaktree Capital Management, managing over $190 billion in alternative investments with a primary focus on distressed debt, high-yield bonds, and opportunistic value equities. His client memos—praised by Warren Buffett as essential reading—form the foundation of modern institutional contrarianism and market cycle analysis (*The Most Important Thing*, 2011; *Mastering the Market Cycle*, 2018).

#### Real-World Core Philosophy
1. **Second-Level Thinking:** First-level thinking is simplistic and superficial: *"It’s a good company; let’s buy the stock."* Second-level thinking is deep, complex, and reflexive: *"It’s a good company, but everyone thinks it’s great, so it’s overpriced and overhyped. Let’s sell."* Conversely: *"It’s a company in a depressed industry facing bad news, but everyone thinks it’s going bankrupt. Expectations are so abysmally low that any stabilization will cause an explosive re-rating. Let’s buy."*
2. **The Definition of Risk (Not Volatility):** Marks fundamentally rejects modern portfolio theory’s equation of risk with standard deviation (volatility). Risk is solely **the probability of permanent capital loss**. A stock experiencing sharp downward volatility because market participants are panicked has actually become *less* risky, provided its solvency is secure.
3. **Risk Control via Broad Diversification:** Contrarian and distressed bets are individually binary and fat-tailed—some companies facing severe despondency really are fatal value traps. Oaktree never concentrates heavily in a tiny handful of names; its public equity books run 40–180 positions across divergent industries. Risk control means ensuring that a false positive cannot do structural damage to the total fund.
4. **The Primacy of Balance Sheet Survivability:** When buying into widespread pessimism, the primary requirement is staying power:
   $$\text{Solvency Moat} = \text{Low Debt} + \text{Positive Operating Cash Flow} + \text{Committed Promoters}$$
   A business with manageable leverage and positive cash flow cannot be forced into bankruptcy or distressed equity dilution during an industry slump.
5. **The Market Cycle & The Panic Premium:** Market prices swing from euphoric greed to irrational despair like a pendulum. Buying when the crowd is terrified offers an asymmetric margin of safety because bad news is already 100% discounted in the price.

---

### 2. The Essence We Capture in Howard Marks

In StockMinds, Howard Marks operates as an **autonomous contrarian value desk** designed to exploit extreme market pessimism on the Nifty 500:

1. **Dual Technical Oversold Hurdle (Stage 1):** Captures multi-horizon despondency rather than a routine daily dip:
   - `rsi_14 < 35.0`: Deeply oversold momentum velocity.
   - `dist_52w_low_pct <= 20.0`: Trading within 20% of 52-week low (prolonged cycle-level gloom).
2. **Balance Sheet & Ownership Moat (Stage 1):**
   - `debt_to_equity < 1.0`: Conservative leverage to survive extended industry downturns.
   - `promoter_holding_pct >= 40.0`: High promoter alignment ensures skin in the game.
3. **Cross-Sectional Contrarian Percentile Composite (Stage 2):**
   - *Oversold Depth Term ($R_{\text{oversold}}$):*
     $$R_{\text{oversold}} = 0.5 \times R(100 - \text{rsi\_14}) + 0.5 \times R(-\text{dist\_52w\_low\_pct})$$
   - *Quality & Solvency Term ($R_{\text{quality}}$):*
     $$\text{quality\_score} = \frac{\text{roce\_pct} \times \max(0.1, \text{cfo\_to\_pat})}{\max(0.1, \text{debt\_to\_equity})}$$
     $$R_{\text{quality}} = \text{Percentile Rank of quality\_score}$$
   - *Macro Panic Multiplier (`panic_mult`):* Derived from the market regime:
     $$\text{panic\_mult} = \begin{cases} 1.25\times & \text{if regime} = \text{PANIC} \\ 1.10\times & \text{if regime} = \text{ELEVATED} \\ 1.00\times & \text{otherwise} \end{cases}$$
   - *Composite Intensity Score:*
     $$\text{intensity\_score} = \min\left(1.0, \; \left(\frac{R_{\text{oversold}} + R_{\text{quality}}}{2}\right) \times \text{panic\_mult}\right)$$
4. **Diversified 8-Stock Portfolio Structure:** In alignment with Oaktree's risk-control doctrine, Marks holds up to 8 concurrent positions with a maximum 12.5% position cap, preventing individual value traps from sinking the book.
5. **Volatility Breathing Room ($2.5\times \text{ATR-14}$):** Distressed entries frequently experience short-term volatility spikes. A $2.5\times \text{ATR}$ stop floor prevents market noise from shaking out positions before mean-reversion occurs.
6. **Fatal Value Trap Veto:** Prompt explicitly directs the LLM to separate temporary cyclical panic (margin squeeze, tariff noise, industry destocking) from permanent impairment (accounting fraud, auditor resignations, SEBI forensic probes, debt default).

---

### 3. Real World vs. Our Implementation: Gaps & Constraints

| Dimension | Real-World Oaktree / Howard Marks | StockMinds Implementation (Howard Marks) | Impact & Rationale |
| :--- | :--- | :--- | :--- |
| **Asset Class** | Primarily distressed debt, senior secured credit, high-yield bonds, and reorganization equity. | Nifty 500 cash equity delivery. | Solvency principles are translated from debt covenants to standardized equity balance-sheet ratios ($\text{D/E}$, $\text{CFO}/\text{PAT}$, $\text{ROCE}$). |
| **Promoter Pledge Data** | Oaktree forensic analysts scrutinize promoter encumbrances and lender collateral liens. | Ingested corporate news headlines and FinBERT sentiment. | As documented in `docs/upstox_findings.md`, structural pledge data is unavailable from the broker API; prompt folds pledge risks into the news forensic veto. |
| **Portfolio Breadth** | 40 to 180 positions across multi-billion-dollar credit funds. | Up to 8 positions in a ₹1,00,000 paper trading book (12.5% cap per ticker). | Scaled for an autonomous desk while preserving Marks' principle that contrarian risk must be broadly diversified. |
| **Holding Period** | 1 to 5 years through full credit and restructuring cycles. | 21 to 120 trading days (`ttl_days = 10`, `lookback_days = 90`, `eval_horizon_days = 60`). | Calibrated for quarterly cyclical sentiment mean-reversion within the system's operational timeframe. |

---

### 4. Metrics & Features Used

| Feature Name | Category | Mathematical Definition | Role in Persona | Match Tolerance |
| :--- | :--- | :--- | :--- | :--- |
| `close` | Price | Daily EOD close in ₹ | Execution reference price | `REL(0.5%)` |
| `rsi_14` | Momentum | Wilder 14-period Relative Strength Index | Deep oversold entry gate ($< 35.0$) | `ABS(2.0)` |
| `dist_52w_low_pct` | Structure | $(C_t - \text{Low}_{52w}) / \text{Low}_{52w} \times 100$ | Proximity to 52-week low hurdle ($\le 20.0\%$) | `ABS(1.0)` |
| `dist_52w_high_pct` | Structure | $(C_t - \text{High}_{52w}) / \text{High}_{52w} \times 100$ | Cycle drawdown depth context | `ABS(1.0)` |
| `debt_to_equity` | Solvency | $\text{Total Debt} / \text{Total Equity}$ | Solvency hurdle ($< 1.0$, ideally $< 0.5$) | `ABS(0.05)` |
| `cfo_to_pat` | Cash Flow | $\text{Cash Flow from Operations} / \text{PAT}$ | Verifies cash reality vs accounting loss ($> 0.6$) | `ABS(0.05)` |
| `roce_pct` | Quality | $\text{EBIT} / (\text{Total Assets} - \text{Current Liabilities}) \times 100$ | Capital productivity in downturn ($\ge 10\%$) | `ABS(1.0)` |
| `promoter_holding_pct`| Ownership | Promoter equity holding percentage | Hurdle ($\ge 40.0\%$); ensures alignment | `ABS(0.5)` |
| `atr_14` | Volatility | Wilder 14-period Average True Range | Volatility breathing stop floor ($2.5\times$) | `REL(5.0%)` |
| `news_sentiment` | Catalyst | FinBERT headline sentiment score $[-1, 1]$ | Detects panic sentiment vs fatal traps | `ABS(0.05)` |
| `regime` | Macro | Market volatility regime (`PANIC`, `ELEVATED`, `NORMAL`) | Scales intensity score during market-wide fear | `EXACT` |
| `india_vix` | Macro | NSE India VIX implied volatility index | Quantifies macro panic temperature | `ABS(0.5)` |

---

### 5. Research Hypotheses & What We Expect to Find

1. **Second-Level Value Trap Filtering:** Does the LLM effectively discriminate between buyable cyclical despondency (e.g. temporary margin compressions) and permanent capital impairment (e.g. governance scandals, auditor exits), correctly outputting `HOLD` on fatal traps?
2. **Panic Regime Asymmetry:** When the macro regime shifts to `PANIC` (India VIX $> 20$), does Marks' ranking multiplier correctly surface high-quality solvent companies dumped during liquidity runs?
3. **Diversification vs. Concentration in Drawdowns:** Does Marks' 8-position portfolio structure exhibit lower maximum drawdown and higher capital survival than concentrated single-name bets when individual contrarian picks take longer to recover?
4. **Mean-Reversion Profit Realization:** Do trades exited via Marks' mean-reversion rules (RSI recovering $> 60$ or testing 50/200 EMA) capture a higher percentage of the recovery bounce than fixed-time systematic stops?

---

## Agent 4: Rakesh Jhunjhunwala (Growth Compounder & Secular Leadership)

| Attribute | Specification |
| :--- | :--- |
| **Agent ID (Database)** | `jhunjhunwala` (LLM Agent: Display Name "Rakesh Jhunjhunwala") |
| **Baseline Status** | LLM-only in MVP (Rules baseline reserved for post-MVP comparison) |
| **Strategy School** | High-Conviction Growth Compounding & Secular Megatrends |
| **Account Capital** | ₹1,00,000 Paper Equity (separate account) |
| **Holding Horizon** | Multi-month / quarterly: 90–180 trading sessions (`ttl_days = 14`, `lookback_days = 150`, `eval_horizon_days = 90`) |
| **Portfolio Capacity** | Up to 6 concurrent open positions (concentrated high-conviction book) |
| **Position Cap** | Maximum 20.0% of portfolio equity per ticker |
| **Target Risk Budget** | 1.50% capital risk per trade |
| **Stop Loss Floor** | Minimum distance $\ge 3.5 \times \text{ATR-14}$ below entry price (widest breathing room) |
| **Target Price Range** | Minimum $1 : 2.0$ Risk-to-Reward ($\approx \text{entry\_high} + 5.0\text{--}8.0 \times \text{ATR-14}$) |
| **News / Narrative Exposure** | Multi-year capex programs, PLI schemes, defense/infra wins (`news_lookback_days = 21`) |
| **Fundamentals Exposure** | 12 quarters of historical statements & ratios (`fundamentals_depth = "12q"`) |

---

### 1. Real-World Inspiration: Rakesh Jhunjhunwala & Rare Enterprises

#### The Person & The Legacy
Rakesh Jhunjhunwala (1960–2022), widely revered as the "Big Bull" of Dalal Street and India's Warren Buffett, was a chartered accountant who began trading in 1985 with ₹5,000 and built an equity portfolio exceeding ₹30,000 crore ($4 billion). Through his firm Rare Enterprises, he championed structural, long-term equity compounding anchored in the Indian economic growth story.

#### Real-World Core Philosophy
1. **Unshakeable Structural Optimism on India:** Jhunjhunwala believed that India was on an unstoppable multi-decade trajectory of economic, industrial, and consumer expansion. He invested aggressively in businesses capitalizing on rising domestic per-capita income (Titan, Metro Brands, Crisil, Indian Hotels) and industrial capacity expansion (Tata Motors, Escorts, NCC).
2. **"Buy Right and Sit Tight":** RJ’s greatest competitive edge was behavioral temperament:
   - He held Titan Company for over two decades through the 2008 global financial crisis, the 2013 gold duty shocks, and the 2020 pandemic crash without liquidating his core holding.
   - He understood that market volatility is simply the price of admission for multi-baggers. Selling a fundamentally sound business simply because its stock dropped 15–20% was anathema to his compounding philosophy.
3. **Promoter Hunger & Skin in the Game:** RJ placed supreme value on management integrity, ambition, and alignment. He avoided promoter-light companies where management acted as hired hands rather than passionate owners. High promoter shareholding was non-negotiable.
4. **Institutional Footprints & Re-Rating Triggers:** He recognized that while individual research uncovers value, massive equity appreciation requires institutional validation. When foreign institutional investors (FIIs) and domestic mutual funds (DIIs) begin accumulating a company with strong earnings acceleration, a multi-year valuation multiple expansion (P/E re-rating) follows.
5. **High Concentration on Top Conviction:** Unlike cautious fund managers who dilute their performance across 50–100 stocks, RJ concentrated capital aggressively into his highest-conviction ideas. At various times, a handful of names represented over 60% of his entire net worth.
6. **Wide Volatility Tolerance:** Jhunjhunwala did not believe in tight technical stops. He gave visionary compounders wide operational leeway, exiting only when the fundamental business thesis permanently broke or promoter integrity failed.

---

### 2. The Essence We Capture in Rakesh Jhunjhunwala

In StockMinds, Rakesh Jhunjhunwala is configured as an **autonomous secular growth compounder** desk operating on the Nifty 500:

1. **Secular Growth & Promoter Hurdle (Stage 1):**
   - `pat_growth_yoy_pct >= 10.0`: Requires confirmed double-digit earnings growth velocity.
   - `promoter_holding_pct >= 40.0`: Non-negotiable promoter alignment hurdle.
   - `volume_surge >= 1.2` & `ema_20_above_50 == True`: Confirms technical trend momentum and accumulation.
   - Stage 0 Rule: Gated by the momentum volume expansion rule (`SMA5(vol) > SMA20(vol)`).
2. **Multi-Factor Growth Compounder Percentile Composite (Stage 2):**
   Candidates are ranked cross-sectionally across four key dimensions:
   - $R_{\text{growth}}$: Percentile rank of quarterly earnings growth (`pat_growth_yoy_pct`).
   - $R_{\text{institutional}}$: Percentile rank of institutional accumulation (`fii_dii_qoq_delta_pct`).
   - $R_{\text{volume}}$: Percentile rank of breakout volume conviction (`volume_surge`).
   - $R_{\text{quality}}$: Percentile rank of return on capital employed (`roce_pct`).
   - *Promoter Alignment Bonus:* If promoter holding $\ge 50\%$, a $10\%$ multiplier is applied:
     $$\text{intensity\_score} = \min\left(1.0, \; \left(\frac{R_{\text{growth}} + R_{\text{inst}} + R_{\text{vol}} + R_{\text{quality}}}{4}\right) \times (1.10 \text{ if } \text{promoter} \ge 50\% \text{ else } 1.0)\right)$$
3. **Explicit "Buy Right and Sit Tight" Prompt Instruction:**
   To counter the LLM's natural tendency to over-trade nightly, the prompt enforces a behavioral discipline clause:
   > *"A declining price alone, in the absence of deteriorating business fundamentals (PAT growth reversal, promoter stake reduction, governance breakdown, or a fatal value trap), is strictly NOT a reason to SELL. Volatility is the price of admission for multi-baggers. Re-affirm the secular thesis before contemplating any exit."*
4. **Concentrated 6-Stock Book (Flat 20% Cap):** Reflecting RJ's concentration philosophy, the agent holds up to 6 positions with a flat 20.0% capital allocation cap per ticker.
5. **Widest Volatility Buffer ($3.0\times \text{ATR-14}$):** To prevent premature noise shakeouts, stops are placed at least $3.0\times \text{ATR-14}$ below entry low.
6. **Secular Breakdown Exits:** Open positions (`pos=held`) are exited only if earnings turn negative across consecutive quarters, promoter integrity is compromised, or an existential regulatory/fraud event occurs.

---

### 3. Real World vs. Our Implementation: Gaps & Constraints

| Dimension | Real-World Rakesh Jhunjhunwala | StockMinds Implementation (Jhunjhunwala) | Impact & Rationale |
| :--- | :--- | :--- | :--- |
| **Holding Duration** | Multi-year to multi-decade (e.g. Titan held 20+ years). | Multi-month / quarterly compounding (90–180 trading sessions; `ttl_days = 14`, `lookback_days = 150`, `eval_horizon_days = 90`). | Practical compromise: models RJ's temperament and stock selection criteria within an automated paper testing timeframe. |
| **Pyramiding on Strength** | Aggressively added to winning positions as cash flow and market strength grew. | Active in prompt & broker: Permitted to add to winning positions (`pos=held`) with positive unrealized PnL when earnings thesis strengthens, subject to the 20.0% max ticker equity cap and broker reserved-cash validations. | Captures the authentic RJ compounding mechanism without risking portfolio concentration breaches. |
| **Management Channel Checks** | Direct personal meetings with promoters, founders, and plant managers. | Ingested corporate news headlines (capex, PLI, order wins) and FinBERT sentiment. | LLM processes textual execution and capex announcements in lieu of direct board-level access. |
| **Leverage** | Periodically used substantial market leverage and futures long positions during bull runs. | 1.0x cash delivery (₹1,00,000 paper equity, no margin borrowing). | Conservative paper account baseline; prevents margin call liquidations. |

---

### 4. Metrics & Features Used

| Feature Name | Category | Mathematical Definition | Role in Persona | Match Tolerance |
| :--- | :--- | :--- | :--- | :--- |
| `close` | Price | Daily EOD close in ₹ | Execution reference price | `REL(0.5%)` |
| `pat_growth_yoy_pct` | Growth | YoY quarterly PAT growth percentage | Hurdle ($\ge 10\%$) & growth velocity ranking | `ABS(1.0)` |
| `promoter_holding_pct`| Ownership | Promoter equity holding percentage | Hurdle ($\ge 40\%$); skin-in-the-game bonus ($\ge 50\%$) | `ABS(0.5)` |
| `fii_dii_qoq_delta_pct`| Ownership | QoQ change in combined FII + DII holding % | Institutional accumulation footprint ranking | `ABS(0.5)` |
| `volume_surge` | Volume | $V_t / \text{SMA}_{20}(V)$ | Breakout volume hurdle ($\ge 1.2\times$) | `REL(5.0%)` |
| `ema_20_above_50` | Trend | Boolean flag ($EMA_{20} > EMA_{50}$) | Hurdle: intermediate upward trend alignment | `EXACT` |
| `roce_pct` | Quality | $\text{EBIT} / (\text{Total Assets} - \text{Current Liabilities}) \times 100$ | Capital return efficiency ranking factor | `ABS(1.0)` |
| `atr_14` | Volatility | Wilder 14-period Average True Range | Widest volatility stop floor ($3.5\times$) | `REL(5.0%)` |
| `news_sentiment` | Catalyst | FinBERT headline sentiment score $[-1, 1]$ | Capex, PLI, and order win catalyst validation | `ABS(0.05)` |
| `dist_52w_high_pct` | Structure | $(C_t - \text{High}_{52w}) / \text{High}_{52w} \times 100$ | Breakout proximity to 52-week highs | `ABS(1.0)` |
| `dist_52w_low_pct` | Structure | $(C_t - \text{Low}_{52w}) / \text{Low}_{52w} \times 100$ | Distance from annual lows | `ABS(1.0)` |

---

### 5. Research Hypotheses & What We Expect to Find

1. **Anti-Impatience Behavioral Efficacy:** Does the explicit "Buy Right and Sit Tight" instruction prevent the LLM from prematurely liquidating winning positions during routine 5–10% market drawdowns?
2. **Institutional Footprint Alpha:** Does incorporating `fii_dii_qoq_delta_pct` into the Stage-2 intensity ranking lead to higher forward returns compared to relying solely on retail volume spikes?
3. **Wide Volatility Stop Survival:** Does the $3.5\times \text{ATR}$ stop floor significantly reduce stop-out frequency on high-growth mid-caps compared to tighter $1.5\times\text{--}2.0\times \text{ATR}$ stops?
4. **Concentrated Capital Compounding:** Does a 6-position book with 20% allocations produce higher upside capture during domestic bull market regimes than diversified 8-to-12 position portfolios?

---

## Agent 5: StockMinds Core (Zerodha Varsity Hybrid)

| Attribute | Specification |
| :--- | :--- |
| **Agent ID (Database)** | `varsity` (LLM Agent: Display Name "StockMinds Core") |
| **Baseline Status** | LLM-only in MVP (Rules baseline reserved for post-MVP comparison) |
| **Strategy School** | Textbook Dual-Confluence Swing Trading (Zerodha Varsity) |
| **Account Capital** | ₹1,00,000 Paper Equity (separate account) |
| **Holding Horizon** | Hybrid swing-to-position: 20–75 trading sessions (`ttl_days = 14`, `lookback_days = 90`, `eval_horizon_days = 20`) |
| **Portfolio Capacity** | Up to 10 concurrent open positions (diversified textbook swing book) |
| **Position Cap** | Maximum 10.0% of portfolio equity per ticker |
| **Target Risk Budget** | 1.0% capital risk per trade (scaled 0.5%–1.5% based on conviction and R:R) |
| **Stop Loss Floor** | Minimum distance $\ge 2.0 \times \text{ATR-14}$ below entry price (or swing low support) |
| **Target Price Range** | Strict minimum $1 : 1.5$ Risk-to-Reward ($\ge \text{entry\_high} + 1.5 \times \text{stop\_distance}$) |
| **News / Narrative Exposure** | Corporate catalyst and recent development validation (`news_lookback_days = 7`) |
| **Fundamentals Exposure** | 8 quarters of historical statements & ratios (`fundamentals_depth = "8q"`) |

---

### 1. Real-World Inspiration: Zerodha Varsity & Textbook Indian Swing Trading

#### The Institution & Philosophy
Zerodha Varsity, created by Karthik Rangappa, is the preeminent open-source financial education curriculum in India. Its modules—specifically Module 1 (Introduction to Stock Markets), Module 2 (Technical Analysis), Module 3 (Fundamental Analysis), and Module 9 (Risk Management & Trading Psychology)—form the canonical framework for Indian retail and proprietary swing trading.

#### Real-World Core Philosophy
1. **The Dual Confluence Mandate:** A trade is valid only when fundamental sanity and technical setups converge:
   - *Fundamentals answer WHAT to trade:* Never buy a company with toxic debt, destroyed earnings, or chronic destruction of capital.
   - *Technicals answer WHEN to trade:* Never buy a fundamentally great company if its price chart is in a confirmed downtrend. Trade only in the direction of the confirmed intermediate trend.
2. **DCF Intrinsic-Value Band Valuation (Module 3, Ch 14–15):**
   Absolute valuation is established using a two-stage Discounted Cash Flow model with a $\pm 10\text{--}15\%$ modeling error band:
   - *Price below the lower band:* Undervalued, margin of safety present, strong buy zone.
   - *Price inside the band:* Fairly valued, hold existing positions, no fresh speculative buys.
   - *Price above the upper band:* Overvalued, exit or take profits.
3. **The 2% Capital Risk Rule & Kelly Criterion (Module 9):**
   The single most important principle in trading survival:
   $$\text{Maximum Risk per Trade} \le 2.0\% \text{ of Account Capital}$$
   This guarantees that even a string of five consecutive losses impairs the account by less than 10%. Furthermore, once a statistically meaningful sample of closed trades ($\ge 10$) exists, position risk is optimized via empirical Half-Kelly sizing:
   $$K = W - \frac{1 - W}{R}, \quad f^* = 0.5 \times K \quad (\text{bounded between } 1.0\% \text{ and } 2.0\%)$$
4. **Strict 1:1.5 Minimum Risk-to-Reward:**
   Every trade setup must mathematically offer at least 1.5 units of potential reward for every 1.0 unit of capital risked:
   $$\frac{\text{target\_price} - \text{entry\_high}}{\text{entry\_low} - \text{stop\_loss\_price}} \ge 1.5$$
   At a $1:1.5$ ratio, a trader achieves profitability with just a $40\%$ win rate:
   $$\text{Expectancy} = (0.40 \times 1.5) - (0.60 \times 1.0) = +0.00 \quad (\text{profitable above } 40\%)$$
5. **Anti-Averaging Bias:**
   Varsity strictly forbids "averaging down" on a losing trade. Averaging down converts a minor disciplined trading loss into a catastrophic capital trap. When the stop is hit, the trader exits immediately without emotion.
6. **Anti-FOMO & Overbought Discipline:**
   Never chase breakouts when the Relative Strength Index (RSI) exceeds 70. Wait for orderly pullbacks to moving average supports before establishing positions.

---

### 2. The Essence We Capture in StockMinds Core

In StockMinds, StockMinds Core acts as the **canonical benchmark swing trader** executing textbook confluence principles:

1. **Dual Confluence Hurdles (Stage 1):**
   - *Technical Gate:* `ema_20_above_50 == True` (confirmed upward trend structure) and `rsi_14 in [45.0, 68.0]` (bullish momentum without exhaustion).
   - *Fundamental Moat Gate:* `roce_pct >= 12.0` (capital productivity), `roe_pct >= 12.0` (shareholder equity return), and `debt_to_equity <= 1.5` (solvent, manageable debt).
2. **Cross-Sectional Confluence Percentile Composite (Stage 2):**
   Candidates are ranked cross-sectionally by harmonizing technical momentum, capital productivity, solvency, and DCF intrinsic fair value:
   - Technical Rank: $R_{\text{tech}} = 0.5 \times R(\text{volume\_surge}) + 0.5 \times R(\text{rsi\_14})$
   - Fundamental Rank: $R_{\text{fund}} = \frac{1}{3} \times R(\text{roce\_pct}) + \frac{1}{3} \times R(1 / \max(0.1, \text{debt\_to\_equity})) + \frac{1}{3} \times R(\text{dcf\_discount\_pct})$
     *(For Financial Services or tickers without valid DCF, $R(\text{dcf\_discount\_pct})$ receives a neutral 0.50 median rank)*.
   - Combined Intensity Score:
     $$\text{intensity\_score} = \min\left(1.0, \; \left(\frac{R_{\text{tech}} + R_{\text{fund}}}{2}\right) \times (1.10 \text{ if } \text{news\_sentiment} > 0.10 \text{ else } 1.0)\right)$$
3. **DCF Valuation Anchor with Estimation Uncertainty:**
   Per-share intrinsic value is computed on a 14-day cadence using bounded capex FCFF, multi-period trailing PAT growth clamped to $[0.0\%, 15.0\%]$, sector-banded discount rates ($11.0\%\text{--}13.5\%$), and primary Market Cap / Price shares derivation. Nightly, `dcf_discount_pct` is derived against the closing price. The LLM is guided that $\pm 15\%$ represents fair value and instructed to prioritize setups where technical momentum and DCF margin of safety agree.
4. **Empirical Kelly Sizing Guidance (Module 9):**
   When closed trade history reaches $\ge 10$ trades, the context assembler dynamically calculates the empirical win rate $W$ and win/loss payoff $R$, providing a Half-Kelly recommended risk budget per trade (clamped to $[1.0\%, 2.0\%]$).
5. **Textbook Mechanical Sizing (Varsity 2% Rule & Half-Kelly):**
   The prompt enforces textbook risk parameters from Zerodha Varsity Module 9: trade risk scaled between 0.5% and 1.5% of account capital (target 1.0%), $2.0\times \text{ATR-14}$ stop floor, $1:1.5$ minimum target ratio, 10.0% max position cap, and up to 10 concurrent diversified positions to eliminate single-stock ruin.
   
> [!NOTE] Primary Origin of the 1:1.5 Risk-to-Reward Floor
   StockMinds Core uses a $1 : 1.5$ RRR floor primary-sourced directly from Zerodha Varsity Module 1 (*The Mathematics of Trading*) and Module 9 (*Risk Management*). Varsity demonstrates that with a disciplined 50% win rate, a 1:1.5 payoff generates positive mathematical expectancy while accommodating substantially higher trade frequency than a strict 1:2.0 floor. In contrast, swing personas (Simons, Lynch, Marks, RJ) enforce a $1 : 2.0$ floor to ensure wide profit margins over market slippage and transaction friction.
6. **Trailing Stops & Profit Protection:**
   The agent is instructed to use the `ADJUST` action to trail stops upward as targets are approached, locking in gains while strictly adhering to the rule that stops may never be widened downward.

---

### 3. Real World vs. Our Implementation: Gaps & Constraints

| Dimension | Real-World Zerodha Varsity Trader | StockMinds Implementation (StockMinds Core) | Impact & Rationale |
| :--- | :--- | :--- | :--- |
| **Chart Pattern Recognition** | Visual identification of classical chart patterns (head & shoulders, flags, double bottoms). | Indicator snapshots: EMA alignment, Wilder RSI-14, volume surge, ATR-14. | Focuses on verifiable quantitative indicators rather than subjective visual chart patterns. |
| **Support & Resistance** | Discretionary horizontal support/resistance lines drawn across historical pivot levels. | Volatility-aware stop floor ($\ge 2.0\times \text{ATR-14}$) below entry low. | Replaces subjective line-drawing with mathematically consistent volatility buffers. |
| **Order Types** | GTT (Good-Till-Triggered) bracket orders on the Zerodha Kite platform. | Paper Broker engine with pending order queue and automated 10-minute monitor loop. | Simulates realistic bracket order execution with slippage and regulatory transaction charges. |

---

### 4. Metrics & Features Used

| Feature Name | Category | Mathematical Definition | Role in Persona | Match Tolerance |
| :--- | :--- | :--- | :--- | :--- |
| `close` | Price | Daily EOD close in ₹ | Execution reference price | `REL(0.5%)` |
| `ema_20_above_50` | Trend | Boolean flag ($EMA_{20} > EMA_{50}$) | Hurdle: intermediate upward trend alignment | `EXACT` |
| `rsi_14` | Momentum | Wilder 14-period Relative Strength Index | Hurdle ($45\text{--}68$); momentum ranking factor | `ABS(2.0)` |
| `volume_surge` | Volume | $V_t / \text{SMA}_{20}(V)$ | Volume breakout ranking factor | `REL(5.0%)` |
| `macd_hist` | Momentum | $(EMA_{12} - EMA_{26}) - EMA_9$ | Momentum confirmation context | `ABS_PCT_CLOSE(0.1)` |
| `roce_pct` | Quality | $\text{EBIT} / (\text{Total Assets} - \text{Current Liabilities}) \times 100$ | Hurdle ($\ge 12\%$); capital productivity ranking | `ABS(1.0)` |
| `roe_pct` | Quality | $\text{PAT} / \text{Equity Capital} \times 100$ | Hurdle ($\ge 12\%$); shareholder return filter | `ABS(1.0)` |
| `debt_to_equity` | Solvency | $\text{Total Debt} / \text{Total Equity}$ | Hurdle ($\le 1.5$); leverage ranking factor | `ABS(0.05)` |
| `dcf_discount_pct` | Valuation | $(\text{IV}_{\text{share}} - \text{Close}) / \text{Close} \times 100$ | Valuation anchor ($\pm 15\%$ fair band); Stage-2 ranking | `ABS(2.0)` |
| `atr_14` | Volatility | Wilder 14-period Average True Range | Volatility stop floor ($2.0\times$) | `REL(5.0%)` |
| `news_sentiment` | Catalyst | FinBERT headline sentiment score $[-1, 1]$ | Catalyst bonus ($> 0.10$) and negative news veto | `ABS(0.05)` |
| `dist_52w_high_pct` | Structure | $(C_t - \text{High}_{52w}) / \text{High}_{52w} \times 100$ | Breakout structure context | `ABS(1.0)` |
| `dist_52w_low_pct` | Structure | $(C_t - \text{Low}_{52w}) / \text{Low}_{52w} \times 100$ | Swing low anchor context | `ABS(1.0)` |

---

### 5. Research Hypotheses & What We Expect to Find

1. **Dual Confluence vs. Pure Strategies:** Does requiring both technical momentum and fundamental solvency produce higher risk-adjusted returns (Sharpe/Sortino) and lower maximum drawdown than pure momentum (Jimmy) or pure contrarian value (Marks)?
2. **Adherence to the 1:1.5 R:R Ratio:** Does the LLM autonomously maintain the $1:1.5$ minimum Risk-to-Reward ratio across its decisions without relying on hardcoded broker clamps?
3. **The 2% Risk Budget Survival:** Does the textbook 2% capital risk rule preserve portfolio equity during market drawdown regimes compared to higher-risk strategies?
4. **Agentic Arithmetic Fidelity:** What is the measured `sizing_fidelity_score` for StockMinds Core when it translates its 2% risk budget and stop distance into position shares?

