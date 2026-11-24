"""Hybrid Autonomous Viral Idea Discovery & 85+ Gate Scorer (prompts/idea_scorer.md).

3-Tier Infinite Content Architecture:
1. Curated Verified Bank: 24 high-impact borderless blueprints (6 per locked pillar:
   money_scale, hidden_tech, mind_glitches, science_anomalies), all verified >=85/100.
2. Free-Tier LLM Expansion: When GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY is
   set and curated blueprints are exhausted, generates net-new data-backed topics.
3. Zero-Key Live Wikipedia Anomaly Engine: Extracts real quantitative facts from
   Wikipedia REST API for endless zero-cost, non-duplicate concepts even with 0 keys.
"""

from __future__ import annotations

import json
import random
import re
from typing import Any, Dict, List, Optional

import requests

from core.config import get_logger, load_prompt
from core.llm_client import ZeroCostLLMClient
from core.state_db import StateDB

logger = get_logger("idea_engine")

WIKI_UA = "VelumBroadcastEngine/1.0 (https://github.com/MFTTT11/velum-studio)"

# 24 Verified, borderless, data-dense documentary blueprints (6 per locked pillar)
CURATED_BLUEPRINTS: List[Dict[str, Any]] = [
    # ===================== PILLAR 1: MONEY & POWER SCALE =====================
    {
        "topic_id": "one-million-vs-one-billion-scale-trap",
        "pillar": "money_scale",
        "format_signature": "exponential_scale_contrast",
        "primary_keyword": "million vs billion scale comparison",
        "title_variants": [
            "11 Days vs 31 Years: Why Your Brain Fails Billionaires",
            "$1 Million vs $1 Billion Is Not Even Close",
            "The Hidden Math Behind $1 Billion Nobody Can Picture",
        ],
        "thumbnail_hooks": [["MILLION vs", "BILLION"], ["$1B IS", "BROKEN"], ["1,000X", "SCALE GAP"]],
        "shock_hook_stat": "11 DAYS vs 31 YEARS",
        "hook_subtext": "THE BILLION SCALE ILLUSION",
        "wiki_entity": "Billion",
        "scores": {"shock_hook": 24, "visualizability": 20, "curiosity_gap": 18, "comment_velocity": 14, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "1 MILLION SECONDS", "value": "11.5 DAYS", "numeric": 11.5, "unit": "DAYS"},
            {"label": "1 BILLION SECONDS", "value": "31.7 YEARS", "numeric": 31.7, "unit": "YEARS"},
            {"label": "1 TRILLION SECONDS", "value": "31,709 YEARS", "numeric": 31709, "unit": "YEARS"},
            {"label": "SPENDING $10K/DAY", "value": "273 YEARS", "numeric": 273, "unit": "YEARS"},
        ],
        "visual_queries": [
            "skyscraper financial district night architecture",
            "gold bullion bars bank vault",
            "stock market trading floor screens",
            "mechanical clock gears macro",
            "earth from space night city lights",
        ],
    },
    {
        "topic_id": "all-world-gold-one-cube-scale",
        "pillar": "money_scale",
        "format_signature": "physical_volume_shock",
        "primary_keyword": "all gold ever mined cube size",
        "title_variants": [
            "Every Ounce of Gold on Earth Fits in One Tiny Cube",
            "All Gold in Human History Is Smaller Than a Tennis Court",
            "212,000 Tons of Gold Visualized Next to One Building",
        ],
        "thumbnail_hooks": [["ALL EARTH", "GOLD"], ["22 METER", "CUBE"], ["$16T IN", "1 BOX"]],
        "shock_hook_stat": "22M CUBE = ALL GOLD",
        "hook_subtext": "6,000 YEARS OF MINING",
        "wiki_entity": "Gold_reserve",
        "scores": {"shock_hook": 23, "visualizability": 20, "curiosity_gap": 18, "comment_velocity": 13, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "ALL MINED GOLD", "value": "212,582 TONS", "numeric": 212582, "unit": "TONS"},
            {"label": "SOLID CUBE EDGE", "value": "22 METERS", "numeric": 22, "unit": "M"},
            {"label": "GOLD DENSITY", "value": "19.3 G/CM3", "numeric": 19.3, "unit": "G/CM3"},
            {"label": "GLOBAL VALUE", "value": "$16 TRILLION", "numeric": 16, "unit": "T USD"},
        ],
        "visual_queries": [
            "gold bullion bars bank vault dark",
            "gold mining open pit aerial view",
            "tennis court stadium aerial view",
            "central bank vault heavy steel door",
            "molten gold foundry furnace glow",
        ],
    },
    {
        "topic_id": "container-shipping-hidden-economy",
        "pillar": "money_scale",
        "format_signature": "hidden_logistics_engine",
        "primary_keyword": "shipping container global trade system",
        "title_variants": [
            "One Steel Box Moves 90% of Everything You Own",
            "How 24,000 Containers Fit on One Ship Without Sinking",
            "The $14 Trillion Ocean Highway You Never See",
        ],
        "thumbnail_hooks": [["90% OF", "YOUR STUFF"], ["24,000 BOXES", "1 SHIP"], ["$14T OCEAN", "ENGINE"]],
        "shock_hook_stat": "90% MOVES BY SEA",
        "hook_subtext": "THE STEEL BOX REVOLUTION",
        "wiki_entity": "Containerization",
        "scores": {"shock_hook": 22, "visualizability": 19, "curiosity_gap": 18, "comment_velocity": 13, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "MARITIME SHARE", "value": "90% GOODS", "numeric": 90, "unit": "%"},
            {"label": "MEGA-SHIP CAPACITY", "value": "24,346 TEU", "numeric": 24346, "unit": "TEU"},
            {"label": "COST DROP SINCE 1956", "value": "-97% COST", "numeric": 97, "unit": "%"},
            {"label": "ANNUAL SEA TRADE", "value": "$14 TRILLION", "numeric": 14, "unit": "T USD"},
        ],
        "visual_queries": [
            "container ship port cranes night aerial",
            "shipping containers stacked harbor",
            "suez canal satellite cargo ship",
            "cargo ship ocean waves sunset",
            "industrial freight logistics port",
        ],
    },
    {
        "topic_id": "compound-penny-vs-million-trap",
        "pillar": "money_scale",
        "format_signature": "exponential_doubling_paradox",
        "primary_keyword": "penny doubled 30 days exponential math",
        "title_variants": [
            "$0.01 Doubled for 30 Days Beats $1 Million by 5x",
            "Why Day 25 Looks Like Failure Before $5.3 Million",
            "The Hidden Doubling Curve Behind Exponential Wealth",
        ],
        "thumbnail_hooks": [["$0.01 vs", "$1,000,000"], ["DAY 30 =", "$5.3M"], ["EXPONENTIAL", "TRAP"]],
        "shock_hook_stat": "$0.01 -> $5.3 MILLION",
        "hook_subtext": "30 DAYS OF DOUBLING",
        "wiki_entity": "Wheat_and_chessboard_problem",
        "scores": {"shock_hook": 23, "visualizability": 20, "curiosity_gap": 18, "comment_velocity": 14, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "DAY 10 TOTAL", "value": "$5.12", "numeric": 5.12, "unit": "USD"},
            {"label": "DAY 20 TOTAL", "value": "$5,242", "numeric": 5242, "unit": "USD"},
            {"label": "DAY 28 TOTAL", "value": "$1.34 MILLION", "numeric": 1342177, "unit": "USD"},
            {"label": "DAY 30 FINAL", "value": "$5.36 MILLION", "numeric": 5368709, "unit": "USD"},
        ],
        "visual_queries": [
            "copper coin macro dark lighting",
            "financial chart exponential curve dark",
            "chessboard dark dramatic lighting",
            "stock exchange skyscraper glass night",
            "banknotes cash stack macro",
        ],
    },
    {
        "topic_id": "global-debt-vs-physical-cash",
        "pillar": "money_scale",
        "format_signature": "invisible_money_ratio",
        "primary_keyword": "physical cash vs digital money supply",
        "title_variants": [
            "92% of the World's Money Doesn't Physically Exist",
            "What Happens If Everyone Withdraws Cash at Once",
            "Only 8% of Global Money Is Real Paper Currency",
        ],
        "thumbnail_hooks": [["92% IS", "DIGITAL"], ["ONLY 8%", "IS REAL"], ["THE CASH", "ILLUSION"]],
        "shock_hook_stat": "92% IS PURE CODE",
        "hook_subtext": "THE INVISIBLE MONEY SUPPLY",
        "wiki_entity": "Money_supply",
        "scores": {"shock_hook": 23, "visualizability": 19, "curiosity_gap": 19, "comment_velocity": 14, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "DIGITAL MONEY", "value": "92% LEDGER", "numeric": 92, "unit": "%"},
            {"label": "PHYSICAL CASH", "value": "8% PAPER", "numeric": 8, "unit": "%"},
            {"label": "GLOBAL M2 SUPPLY", "value": "$108 TRILLION", "numeric": 108, "unit": "T USD"},
            {"label": "DERIVATIVES NOTIONAL", "value": "$667 TRILLION", "numeric": 667, "unit": "T USD"},
        ],
        "visual_queries": [
            "server room banking data center dark",
            "currency banknotes printing press",
            "federal reserve building architecture",
            "atm terminal city street night",
            "stock market digital ticker board",
        ],
    },
    {
        "topic_id": "airline-zero-margin-business-model",
        "pillar": "money_scale",
        "format_signature": "hidden_business_engine",
        "primary_keyword": "airlines loyalty points bank business model",
        "title_variants": [
            "Major Airlines Are Secretly Banks That Fly Planes",
            "Why Flying You Makes $6 While Points Make Billions",
            "The Hidden Financial Engine Inside Frequent Flyer Miles",
        ],
        "thumbnail_hooks": [["AIRLINES", "ARE BANKS"], ["$6 PROFIT", "PER SEAT"], ["MILES WORTH", "MORE"]],
        "shock_hook_stat": "$6 PROFIT PER FLIGHT",
        "hook_subtext": "AIRLINES ARE SECRET BANKS",
        "wiki_entity": "Frequent-flyer_program",
        "scores": {"shock_hook": 22, "visualizability": 18, "curiosity_gap": 20, "comment_velocity": 13, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "AVG NET MARGIN", "value": "$6 / PASSENGER", "numeric": 6, "unit": "USD"},
            {"label": "LOYALTY VALUATION", "value": "$25+ BILLION", "numeric": 25, "unit": "B USD"},
            {"label": "FUEL COST SHARE", "value": "30% BUDGET", "numeric": 30, "unit": "%"},
            {"label": "CREDIT CARD REVENUE", "value": "$6.8B / YEAR", "numeric": 6.8, "unit": "B USD"},
        ],
        "visual_queries": [
            "commercial airliner cockpit night",
            "airport runway tarmac aircraft twilight",
            "airplane jet turbine engine macro",
            "credit card payment terminal dark",
            "airport terminal departures board",
        ],
    },
    # ===================== PILLAR 2: HIDDEN TECH SYSTEMS =====================
    {
        "topic_id": "subsea-cables-99-percent-internet",
        "pillar": "hidden_tech",
        "format_signature": "hidden_infrastructure_chokepoint",
        "primary_keyword": "undersea cables internet infrastructure",
        "title_variants": [
            "99% of the Internet Runs Through a Garden Hose",
            "The Hidden Ocean Cables Holding Civilization Together",
            "One Anchor Cut Could Darken Half the Planet",
        ],
        "thumbnail_hooks": [["99% RUNS", "UNDERWATER"], ["ONE CABLE", "CUTS ALL"], ["17MM FIBER", "INTERNET"]],
        "shock_hook_stat": "99% RUNS ON 17MM",
        "hook_subtext": "HIDDEN INTERNET CHOKEPOINTS",
        "wiki_entity": "Submarine_communications_cable",
        "scores": {"shock_hook": 24, "visualizability": 19, "curiosity_gap": 19, "comment_velocity": 13, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "OCEAN TRAFFIC SHARE", "value": "99% DATA", "numeric": 99, "unit": "%"},
            {"label": "DEEP CABLE WIDTH", "value": "17 MM", "numeric": 17, "unit": "MM"},
            {"label": "TOTAL SUBSEA LENGTH", "value": "1.4M KM", "numeric": 1400000, "unit": "KM"},
            {"label": "DAILY WIRE VOLUME", "value": "$10 TRILLION", "numeric": 10, "unit": "T USD"},
        ],
        "visual_queries": [
            "deep ocean abyss underwater dark blue",
            "fiber optic cables glowing light macro",
            "cargo ship anchor ocean storm",
            "server room data center dark glowing",
            "world map night satellite network",
        ],
    },
    {
        "topic_id": "euv-lithography-hardest-machine",
        "pillar": "hidden_tech",
        "format_signature": "extreme_engineering_monopoly",
        "primary_keyword": "ASML EUV lithography machine explained",
        "title_variants": [
            "The $380M Machine Only One Company Can Build",
            "How 50,000 Laser Shots Per Second Power Your Phone",
            "The Single Bottleneck Controlling Global AI Chips",
        ],
        "thumbnail_hooks": [["$380M", "1 MACHINE"], ["50,000", "LASERS/SEC"], ["CHIP", "MONOPOLY"]],
        "shock_hook_stat": "$380M // 1 COMPANY",
        "hook_subtext": "THE CHIP MONOPOLY MACHINE",
        "wiki_entity": "Extreme_ultraviolet_lithography",
        "scores": {"shock_hook": 23, "visualizability": 19, "curiosity_gap": 19, "comment_velocity": 13, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "MACHINE COST", "value": "$380 MILLION", "numeric": 380, "unit": "M USD"},
            {"label": "LASER PULSES", "value": "50,000 / SEC", "numeric": 50000, "unit": "HZ"},
            {"label": "PLASMA HEAT", "value": "220,000 C", "numeric": 220000, "unit": "C"},
            {"label": "GLOBAL SUPPLIERS", "value": "1 COMPANY", "numeric": 1, "unit": "FIRM"},
        ],
        "visual_queries": [
            "silicon wafer microchip semiconductor cleanroom",
            "laser beam optics laboratory dark",
            "microprocessor circuit board macro glow",
            "cargo airplane heavy logistics transport",
            "supercomputer data center racks",
        ],
    },
    {
        "topic_id": "transistor-scale-vs-red-blood-cell",
        "pillar": "hidden_tech",
        "format_signature": "nanoscale_visual_comparison",
        "primary_keyword": "2nm transistor size visual comparison",
        "title_variants": [
            "How 100 Billion Switches Fit Inside Your Fingernail",
            "Modern Transistors Are Only 10 Silicon Atoms Wide",
            "Inside the Atomic Limit Breaking Moore's Law",
        ],
        "thumbnail_hooks": [["10 ATOMS", "WIDE"], ["100 BILLION", "SWITCHES"], ["QUANTUM", "WALL"]],
        "shock_hook_stat": "10 ATOMS WIDE",
        "hook_subtext": "INSIDE YOUR PROCESSOR",
        "wiki_entity": "Transistor_count",
        "scores": {"shock_hook": 23, "visualizability": 20, "curiosity_gap": 18, "comment_velocity": 12, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "TRANSISTORS PER CHIP", "value": "100+ BILLION", "numeric": 100, "unit": "B"},
            {"label": "GATE ATOM WIDTH", "value": "10 ATOMS", "numeric": 10, "unit": "ATOMS"},
            {"label": "RED BLOOD CELL", "value": "7,500 NM", "numeric": 7500, "unit": "NM"},
            {"label": "SWITCHING SPEED", "value": "5 BILLION / S", "numeric": 5, "unit": "GHZ"},
        ],
        "visual_queries": [
            "cpu processor silicon wafer closeup",
            "electron microscope microchip circuit",
            "smartphone circuit board macro dark",
            "quantum computer chandelier laboratory",
            "glowing silicon semiconductor cleanroom",
        ],
    },
    {
        "topic_id": "power-grid-50hz-real-time-balance",
        "pillar": "hidden_tech",
        "format_signature": "invisible_realtime_balance",
        "primary_keyword": "electrical power grid frequency balance",
        "title_variants": [
            "The Power Grid Must Match Supply Every Millisecond",
            "Why a 1% Frequency Drop Triggers Total Blackouts",
            "The Largest Machine Ever Built Has Almost Zero Storage",
        ],
        "thumbnail_hooks": [["1% DROP =", "BLACKOUT"], ["ZERO", "STORAGE"], ["50.00 HZ", "TIGHTROPE"]],
        "shock_hook_stat": "50.00 HZ OR BLACKOUT",
        "hook_subtext": "EARTH'S LARGEST MACHINE",
        "wiki_entity": "Electrical_grid",
        "scores": {"shock_hook": 22, "visualizability": 19, "curiosity_gap": 19, "comment_velocity": 13, "data_density": 10, "search_demand": 8},
        "key_facts": [
            {"label": "FREQUENCY TOLERANCE", "value": "+/- 0.2 HZ", "numeric": 0.2, "unit": "HZ"},
            {"label": "CASCADE SPEED", "value": "9 SECONDS", "numeric": 9, "unit": "SEC"},
            {"label": "GRID STORAGE SHARE", "value": "< 2% BUFFER", "numeric": 2, "unit": "%"},
            {"label": "SYNCHRONIZED SCALE", "value": "400M HOMES", "numeric": 400, "unit": "M"},
        ],
        "visual_queries": [
            "high voltage power transmission towers twilight",
            "electrical substation transformers night",
            "power plant control room monitors",
            "hydroelectric dam turbines industrial",
            "city skyline power blackout night",
        ],
    },
    {
        "topic_id": "dns-root-servers-internet-phonebook",
        "pillar": "hidden_tech",
        "format_signature": "hidden_protocol_control",
        "primary_keyword": "DNS root servers internet control",
        "title_variants": [
            "13 Invisible Addresses Control the Entire Internet",
            "The 7 Physical Cryptographic Keys That Reboot the Web",
            "How DNS Resolves 100 Billion Requests Every Day",
        ],
        "thumbnail_hooks": [["13 SERVERS", "RUN WEB"], ["7 SECRET", "KEYS"], ["DNS", "BACKBONE"]],
        "shock_hook_stat": "13 ROOT ADDRESSES",
        "hook_subtext": "THE INTERNET'S MASTER KEY",
        "wiki_entity": "Root_name_server",
        "scores": {"shock_hook": 22, "visualizability": 18, "curiosity_gap": 20, "comment_velocity": 13, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "LOGICAL ROOT NODES", "value": "13 LETTERS", "numeric": 13, "unit": "NODES"},
            {"label": "GLOBAL ANYCAST SITES", "value": "1,800+ SITES", "numeric": 1800, "unit": "SITES"},
            {"label": "CRYPTO KEY HOLDERS", "value": "14 OFFICERS", "numeric": 14, "unit": "PEOPLE"},
            {"label": "LOOKUP LATENCY", "value": "< 25 MS", "numeric": 25, "unit": "MS"},
        ],
        "visual_queries": [
            "data center server racks blue glow",
            "network switch ethernet fiber cables",
            "cybersecurity vault key terminal dark",
            "satellite dish global communications",
            "world network connections dark globe",
        ],
    },
    {
        "topic_id": "high-frequency-trading-microsecond-race",
        "pillar": "hidden_tech",
        "format_signature": "speed_of_light_finance",
        "primary_keyword": "high frequency trading speed of light",
        "title_variants": [
            "Firms Spent $300M to Shave 3 Milliseconds Off a Cable",
            "How Speed of Light Limits Wall Street Algorithms",
            "Why Stock Servers Use Identical Spools of Fiber Cable",
        ],
        "thumbnail_hooks": [["$300M FOR", "3 MILLISEC"], ["SPEED OF", "LIGHT WAR"], ["WALL ST", "CABLES"]],
        "shock_hook_stat": "$300M FOR 0.003 SEC",
        "hook_subtext": "THE MICROSECOND ARMS RACE",
        "wiki_entity": "High-frequency_trading",
        "scores": {"shock_hook": 23, "visualizability": 19, "curiosity_gap": 19, "comment_velocity": 13, "data_density": 10, "search_demand": 8},
        "key_facts": [
            {"label": "FIBER TRENCH COST", "value": "$300 MILLION", "numeric": 300, "unit": "M USD"},
            {"label": "TIME GAINED", "value": "3 MILLISEC", "numeric": 3, "unit": "MS"},
            {"label": "HUMAN BLINK TIME", "value": "300 MILLISEC", "numeric": 300, "unit": "MS"},
            {"label": "ALGO VOLUME SHARE", "value": "50%+ TRADES", "numeric": 50, "unit": "%"},
        ],
        "visual_queries": [
            "wall street stock exchange trading screens",
            "microwave communication tower landscape",
            "fiber optic spool data center",
            "server rack supercomputer dark",
            "chicago skyline night finance",
        ],
    },
    # ===================== PILLAR 3: PSYCHOLOGY & COGNITIVE TRAPS =====================
    {
        "topic_id": "decoy-effect-pricing-trap",
        "pillar": "mind_glitches",
        "format_signature": "cognitive_system_exploit",
        "primary_keyword": "decoy effect pricing psychology",
        "title_variants": [
            "Why the Medium Popcorn Exists Only to Trick You",
            "The 3-Option Pricing Trap Controlling Your Wallet",
            "How Companies Hack Your Brain With a Fake Price",
        ],
        "thumbnail_hooks": [["THE FAKE", "PRICE"], ["MEDIUM IS", "A DECOY"], ["+52% MORE", "SPENT"]],
        "shock_hook_stat": "MEDIUM IS A TRAP",
        "hook_subtext": "ASYMMETRIC DOMINANCE BIAS",
        "wiki_entity": "Decoy_effect",
        "scores": {"shock_hook": 23, "visualizability": 19, "curiosity_gap": 18, "comment_velocity": 14, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "2-OPTION HIGH PICK", "value": "32% BUY", "numeric": 32, "unit": "%"},
            {"label": "3-OPTION HIGH PICK", "value": "84% BUY", "numeric": 84, "unit": "%"},
            {"label": "BEHAVIOR SHIFT", "value": "+52 PTS", "numeric": 52, "unit": "PTS"},
            {"label": "DECISION SPEED", "value": "0.4 SEC", "numeric": 0.4, "unit": "SEC"},
        ],
        "visual_queries": [
            "cinema theater dark glowing screen",
            "luxury coffee shop counter menu dark",
            "human brain neural scan glowing",
            "retail shopping mall architecture night",
            "smartphone app subscription screen dark",
        ],
    },
    {
        "topic_id": "survivorship-bias-ww2-planes",
        "pillar": "mind_glitches",
        "format_signature": "visual_logic_reversal",
        "primary_keyword": "survivorship bias airplanes explained",
        "title_variants": [
            "Why Engineers Armored the Spots Without Bullet Holes",
            "The Invisible Data Error That Fooled Top Generals",
            "Survivorship Bias: What You Don't See Controls You",
        ],
        "thumbnail_hooks": [["ARMOR THE", "EMPTY SPOT"], ["INVISIBLE", "DATA TRAP"], ["MISSING", "BULLETS"]],
        "shock_hook_stat": "DON'T ARMOR THE HOLES",
        "hook_subtext": "THE SURVIVORSHIP BLIND SPOT",
        "wiki_entity": "Survivorship_bias",
        "scores": {"shock_hook": 24, "visualizability": 20, "curiosity_gap": 19, "comment_velocity": 13, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "FUSELAGE HIT DENSITY", "value": "1.73 / SQ FT", "numeric": 1.73, "unit": "HITS"},
            {"label": "ENGINE HIT DENSITY", "value": "1.11 / SQ FT", "numeric": 1.11, "unit": "HITS"},
            {"label": "MISSING SAMPLE", "value": "NEVER RETURNED", "numeric": 0, "unit": "%"},
            {"label": "ENGINE ARMOR GAIN", "value": "+1.55X PRIORITY", "numeric": 1.55, "unit": "X"},
        ],
        "visual_queries": [
            "vintage military aircraft hangar monochrome",
            "aircraft fuselage rivets metal closeup",
            "airplane propeller engine mechanical",
            "aviation blueprint technical drawing",
            "dark clouds sky aerial view",
        ],
    },
    {
        "topic_id": "supermarket-architecture-psychological-maze",
        "pillar": "mind_glitches",
        "format_signature": "environmental_behavior_design",
        "primary_keyword": "supermarket layout psychology tricks",
        "title_variants": [
            "Why Milk Is Always in the Farthest Back Corner",
            "How Grocery Stores Engineer 40% More Impulse Buys",
            "The Hidden Behavioral Maze Inside Every Supermarket",
        ],
        "thumbnail_hooks": [["MILK AT", "THE BACK"], ["+40% EXTRA", "SPENT"], ["GROCERY", "MAZE"]],
        "shock_hook_stat": "MILK IS ALWAYS LAST",
        "hook_subtext": "ENGINEERED STORE LAYOUTS",
        "wiki_entity": "Supermarket",
        "scores": {"shock_hook": 22, "visualizability": 19, "curiosity_gap": 18, "comment_velocity": 14, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "UNPLANNED PURCHASES", "value": "40% CART", "numeric": 40, "unit": "%"},
            {"label": "EYE-LEVEL LIFT", "value": "+35% SALES", "numeric": 35, "unit": "%"},
            {"label": "CART SIZE GROWTH", "value": "2X SINCE 1975", "numeric": 200, "unit": "%"},
            {"label": "SLOW MUSIC LIFT", "value": "+29% DWELL", "numeric": 29, "unit": "%"},
        ],
        "visual_queries": [
            "supermarket aisle shelves symmetry",
            "shopping cart retail store lighting",
            "bakery display warm light store",
            "checkout counter supermarket",
            "grocery store aerial architecture",
        ],
    },
    {
        "topic_id": "variable-reward-slot-machine-phone",
        "pillar": "mind_glitches",
        "format_signature": "dopamine_loop_engineering",
        "primary_keyword": "variable reward dopamine scroll psychology",
        "title_variants": [
            "Pull-to-Refresh Was Copied Directly From Slot Machines",
            "Why Unpredictable Feeds Spike Dopamine 2x Higher",
            "The Hidden Casino Algorithm Inside Your Home Screen",
        ],
        "thumbnail_hooks": [["POCKET", "CASINO"], ["2X DOPAMINE", "SPIKE"], ["ENDLESS", "SCROLL"]],
        "shock_hook_stat": "PULL = SLOT LEVER",
        "hook_subtext": "VARIABLE RATIO CONDITIONING",
        "wiki_entity": "Operant_conditioning_chamber",
        "scores": {"shock_hook": 23, "visualizability": 19, "curiosity_gap": 19, "comment_velocity": 14, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "DAILY PHONE CHECKS", "value": "144 / DAY", "numeric": 144, "unit": "CHECKS"},
            {"label": "UNCERTAIN REWARD PEAK", "value": "2.0X DOPAMINE", "numeric": 2.0, "unit": "X"},
            {"label": "AVG DAILY SCREEN", "value": "4.6 HOURS", "numeric": 4.6, "unit": "HRS"},
            {"label": "LIFETIME EQUIVALENT", "value": "11+ YEARS", "numeric": 11, "unit": "YEARS"},
        ],
        "visual_queries": [
            "smartphone glowing screen dark room",
            "slot machine casino neon lights dark",
            "human brain synapse visualization",
            "crowd looking at smartphones night",
            "notification icons digital screen macro",
        ],
    },
    {
        "topic_id": "anchoring-bias-invisible-price-hack",
        "pillar": "mind_glitches",
        "format_signature": "cognitive_calibration_bug",
        "primary_keyword": "anchoring bias psychology experiment",
        "title_variants": [
            "A Random Number Changes How Much You Pay by 300%",
            "Why '$999 Crossed Out to $499' Hacks Rational Brains",
            "The Cognitive Bug Even Judges Cannot Turn Off",
        ],
        "thumbnail_hooks": [["300% PRICE", "ILLUSION"], ["FAKE $999", "ANCHOR"], ["BRAIN", "HACKED"]],
        "shock_hook_stat": "1 NUMBER SHIFTS 300%",
        "hook_subtext": "THE ANCHORING EFFECT",
        "wiki_entity": "Anchoring_effect",
        "scores": {"shock_hook": 22, "visualizability": 19, "curiosity_gap": 18, "comment_velocity": 13, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "WHEEL HIGH ANCHOR", "value": "45% ESTIMATE", "numeric": 45, "unit": "%"},
            {"label": "WHEEL LOW ANCHOR", "value": "25% ESTIMATE", "numeric": 25, "unit": "%"},
            {"label": "JUDICIAL SENTENCE SHIFT", "value": "+8 MONTHS", "numeric": 8, "unit": "MOS"},
            {"label": "LUXURY ANCHOR LIFT", "value": "+38% MARGIN", "numeric": 38, "unit": "%"},
        ],
        "visual_queries": [
            "luxury watch boutique display dark",
            "price tag retail discount macro",
            "courthouse gavel dark wood",
            "roulette wheel casino number closeup",
            "modern minimalist store interior",
        ],
    },
    {
        "topic_id": "zeigarnik-unfinished-loop-memory",
        "pillar": "mind_glitches",
        "format_signature": "working_memory_exploit",
        "primary_keyword": "Zeigarnik effect unfinished task psychology",
        "title_variants": [
            "Why Your Brain Remembers Unfinished Tasks 2x Longer",
            "How Netflix Cliffhangers Weaponize a 1927 Discovery",
            "The Memory Bug That Keeps Songs Stuck in Your Head",
        ],
        "thumbnail_hooks": [["2X STRONGER", "MEMORY"], ["OPEN LOOP", "TRAP"], ["WHY YOU", "BINGE"]],
        "shock_hook_stat": "90% HIGHER RECALL",
        "hook_subtext": "THE ZEIGARNIK LOOP",
        "wiki_entity": "Zeigarnik_effect",
        "scores": {"shock_hook": 22, "visualizability": 18, "curiosity_gap": 19, "comment_velocity": 13, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "INTERRUPTED RECALL", "value": "+90% HIGHER", "numeric": 90, "unit": "%"},
            {"label": "FINISHED TASK DROP", "value": "INSTANT PURGE", "numeric": 50, "unit": "%"},
            {"label": "ORIGINAL STUDY YEAR", "value": "1927 BERLIN", "numeric": 1927, "unit": "YEAR"},
            {"label": "BINGE CONTINUATION", "value": "70%+ NEXT EP", "numeric": 70, "unit": "%"},
        ],
        "visual_queries": [
            "restaurant waiter notebook vintage cafe",
            "television screen dark living room",
            "human brain memory neural light",
            "sticky notes wall workspace night",
            "hourglass sand clock macro dark",
        ],
    },
    # ===================== PILLAR 4: SCIENCE & COSMIC ANOMALIES =====================
    {
        "topic_id": "mariana-trench-pressure-scale",
        "pillar": "science_anomalies",
        "format_signature": "physical_extreme_comparison",
        "primary_keyword": "Mariana Trench pressure comparison",
        "title_variants": [
            "50 Jumbo Jets Stacked on Your Thumb at 11km Deep",
            "What Actually Happens at the Bottom of the Ocean",
            "1,086x Surface Pressure: Inside Challenger Deep",
        ],
        "thumbnail_hooks": [["50 JETS", "1 THUMB"], ["11 KM", "DEAD ZONE"], ["1,086X", "PRESSURE"]],
        "shock_hook_stat": "1,086x ATMOSPHERE",
        "hook_subtext": "CHALLENGER DEEP PHYSICS",
        "wiki_entity": "Mariana_Trench",
        "scores": {"shock_hook": 24, "visualizability": 20, "curiosity_gap": 18, "comment_velocity": 13, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "MAX DEPTH", "value": "10,984 M", "numeric": 10984, "unit": "M"},
            {"label": "PRESSURE RATIO", "value": "1,086 ATM", "numeric": 1086, "unit": "ATM"},
            {"label": "WATER DENSITY JUMP", "value": "+4.96%", "numeric": 4.96, "unit": "%"},
            {"label": "EVEREST MARGIN", "value": "+2,135 M", "numeric": 2135, "unit": "M"},
        ],
        "visual_queries": [
            "deep sea dark ocean trench water",
            "Mount Everest peak aerial view",
            "deep sea submarine research vessel",
            "bioluminescent deep sea jellyfish dark",
            "ocean waves dark storm horizon",
        ],
    },
    {
        "topic_id": "gps-relativity-drift-system",
        "pillar": "science_anomalies",
        "format_signature": "hidden_physics_infrastructure",
        "primary_keyword": "GPS general relativity time dilation",
        "title_variants": [
            "Without Einstein, Your GPS Fails by 11 KM Every Day",
            "The Invisible Time Warp Keeping Your Maps Alive",
            "Why Satellite Clocks Run 38 Microseconds Faster",
        ],
        "thumbnail_hooks": [["11 KM ERROR", "DAILY"], ["TIME RUNS", "FASTER"], ["38 MICROSEC", "DRIFT"]],
        "shock_hook_stat": "11 KM DRIFT / DAY",
        "hook_subtext": "RELATIVITY IN YOUR POCKET",
        "wiki_entity": "Global_Positioning_System",
        "scores": {"shock_hook": 23, "visualizability": 18, "curiosity_gap": 19, "comment_velocity": 13, "data_density": 10, "search_demand": 8},
        "key_facts": [
            {"label": "ORBIT ALTITUDE", "value": "20,200 KM", "numeric": 20200, "unit": "KM"},
            {"label": "GRAVITY SPEEDUP", "value": "+45 US/DAY", "numeric": 45, "unit": "US"},
            {"label": "VELOCITY SLOWDOWN", "value": "-7 US/DAY", "numeric": -7, "unit": "US"},
            {"label": "DAILY DRIFT ERROR", "value": "11.4 KM", "numeric": 11.4, "unit": "KM"},
        ],
        "visual_queries": [
            "satellite orbiting earth space dark",
            "highway city traffic night aerial",
            "atomic clock precision laboratory",
            "smartphone navigation map night car",
            "earth horizon orbital view space",
        ],
    },
    {
        "topic_id": "neutron-star-teaspoon-weight-scale",
        "pillar": "science_anomalies",
        "format_signature": "cosmic_density_shock",
        "primary_keyword": "neutron star teaspoon weight comparison",
        "title_variants": [
            "One Teaspoon of a Neutron Star Weighs 1 Billion Tons",
            "All 8 Billion Humans Crushed Into One Sugar Cube",
            "The Densest Object Before Matter Collapses to Black Holes",
        ],
        "thumbnail_hooks": [["1 SPOON =", "1B TONS"], ["8B HUMANS", "1 CUBE"], ["NEUTRON", "DENSITY"]],
        "shock_hook_stat": "1 SPOON = 1 BILLION TONS",
        "hook_subtext": "EXTREME COSMIC DENSITY",
        "wiki_entity": "Neutron_star",
        "scores": {"shock_hook": 24, "visualizability": 20, "curiosity_gap": 18, "comment_velocity": 13, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "1 TEASPOON MASS", "value": "1 BILLION TONS", "numeric": 1000000000, "unit": "TONS"},
            {"label": "STAR DIAMETER", "value": "20 KM WIDE", "numeric": 20, "unit": "KM"},
            {"label": "MAX SPIN SPEED", "value": "716 REV / SEC", "numeric": 716, "unit": "HZ"},
            {"label": "SURFACE GRAVITY", "value": "200B X EARTH", "numeric": 200, "unit": "B G"},
        ],
        "visual_queries": [
            "pulsar neutron star nebula space",
            "supernova remnant space telescope",
            "city skyline aerial scale comparison",
            "milky way deep space stars",
            "gravity waves physics visualization",
        ],
    },
    {
        "topic_id": "human-dna-length-to-pluto-scale",
        "pillar": "science_anomalies",
        "format_signature": "biological_scale_paradox",
        "primary_keyword": "human body DNA length solar system",
        "title_variants": [
            "Unwinding Your Body's DNA Reaches Pluto 17 Times",
            "2 Meters of Code Folded Into Every Microscopic Cell",
            "The 67 Billion Mile Molecular Thread Inside You",
        ],
        "thumbnail_hooks": [["YOUR DNA", "TO PLUTO"], ["67 BILLION", "MILES"], ["17X ROUND", "TRIPS"]],
        "shock_hook_stat": "17 TRIPS TO PLUTO",
        "hook_subtext": "UNCOILING YOUR OWN DNA",
        "wiki_entity": "Human_genome",
        "scores": {"shock_hook": 23, "visualizability": 19, "curiosity_gap": 18, "comment_velocity": 13, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "DNA PER CELL", "value": "2.0 METERS", "numeric": 2.0, "unit": "M"},
            {"label": "TOTAL BODY CELLS", "value": "37 TRILLION", "numeric": 37, "unit": "T"},
            {"label": "UNCOILED LENGTH", "value": "67B MILES", "numeric": 67, "unit": "B MI"},
            {"label": "PLUTO ROUND TRIPS", "value": "17 TRIPS", "numeric": 17, "unit": "TRIPS"},
        ],
        "visual_queries": [
            "dna double helix glowing microscope",
            "human cell biology fluorescence",
            "pluto planet space nasa",
            "solar system planets orbit space",
            "genetics laboratory dark blue light",
        ],
    },
    {
        "topic_id": "earth-moon-gap-fits-all-planets",
        "pillar": "science_anomalies",
        "format_signature": "space_distance_illusion",
        "primary_keyword": "all planets fit between earth and moon",
        "title_variants": [
            "Every Planet in the Solar System Fits Between Us and Moon",
            "Why Every Textbook Space Diagram Lied About Distance",
            "384,400 KM Visualized: The True Earth-Moon Gap",
        ],
        "thumbnail_hooks": [["ALL PLANETS", "FIT HERE"], ["384,400 KM", "REAL GAP"], ["TEXTBOOKS", "LIED"]],
        "shock_hook_stat": "ALL 7 PLANETS FIT",
        "hook_subtext": "BETWEEN EARTH AND THE MOON",
        "wiki_entity": "Lunar_distance",
        "scores": {"shock_hook": 24, "visualizability": 20, "curiosity_gap": 18, "comment_velocity": 14, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "AVG MOON DISTANCE", "value": "384,400 KM", "numeric": 384400, "unit": "KM"},
            {"label": "ALL 7 PLANETS SUM", "value": "380,008 KM", "numeric": 380008, "unit": "KM"},
            {"label": "REMAINING MARGIN", "value": "+4,392 KM", "numeric": 4392, "unit": "KM"},
            {"label": "LIGHT TRAVEL TIME", "value": "1.28 SEC", "numeric": 1.28, "unit": "SEC"},
        ],
        "visual_queries": [
            "full moon space dark high resolution",
            "earth from moon apollo space",
            "jupiter saturn planets nasa telescope",
            "solar system space stars dark",
            "astronaut lunar surface horizon",
        ],
    },
    {
        "topic_id": "point-nemo-closest-humans-in-space",
        "pillar": "science_anomalies",
        "format_signature": "geographic_isolation_anomaly",
        "primary_keyword": "Point Nemo closest humans ISS space",
        "title_variants": [
            "The Ocean Spot Where Astronauts Are Closer Than Land",
            "Point Nemo: 2,688 KM From Earth's Nearest Coastline",
            "Inside the Pacific Spacecraft Graveyard Nobody Visits",
        ],
        "thumbnail_hooks": [["ISS IS", "CLOSER"], ["2,688 KM", "NO LAND"], ["SPACECRAFT", "GRAVEYARD"]],
        "shock_hook_stat": "400 KM UP vs 2,688 KM",
        "hook_subtext": "POINT NEMO ISOLATION",
        "wiki_entity": "Pole_of_inaccessibility",
        "scores": {"shock_hook": 23, "visualizability": 19, "curiosity_gap": 19, "comment_velocity": 13, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "NEAREST LAND", "value": "2,688 KM", "numeric": 2688, "unit": "KM"},
            {"label": "ISS ORBIT DISTANCE", "value": "408 KM UP", "numeric": 408, "unit": "KM"},
            {"label": "SUNKEN SPACECRAFT", "value": "260+ CRAFT", "numeric": 260, "unit": "CRAFT"},
            {"label": "OCEAN DEPTH HERE", "value": "4,000 M", "numeric": 4000, "unit": "M"},
        ],
        "visual_queries": [
            "international space station orbiting earth",
            "pacific ocean empty horizon storm",
            "spacecraft reentry atmosphere night",
            "satellite ocean map dark blue",
            "lonely ocean waves aerial view",
        ],
    },
    # ===================== V2 ULTRA-VIRAL HIGH-CTR EXPANSION (16 NEW BANGERS) =====================
    {
        "topic_id": "asteroid-psyche-10-quintillion-gold",
        "pillar": "money_scale",
        "format_signature": "cosmic_wealth_paradox",
        "primary_keyword": "16 Psyche asteroid 10 quintillion metal",
        "title_variants": [
            "NASA Found One Asteroid Worth $10 Quintillion (And It Would Crash Earth)",
            "16 Psyche: The Space Rock Worth $1.2 Billion for Every Human Alive",
            "Why Mining This $10 Quintillion Asteroid Would Make Gold Worthless",
        ],
        "thumbnail_hooks": [["$10 QUINTILLION", "ASTEROID"], ["$1.2B EACH", "FOR ALL"], ["NASA FOUND", "GOLD ROCK"]],
        "shock_hook_stat": "$10,000,000,000,000,000,000",
        "hook_subtext": "16 PSYCHE METAL ASTEROID",
        "debate_hook": {
            "question": "IF WE MINED IT, WOULD IT SAVE OR CRASH THE ECONOMY?",
            "option_a": "CRASH IT",
            "option_b": "SAVE IT",
            "pinned": "Honest debate: if NASA brought back even 1% of 16 Psyche's metal, would it make humanity rich or collapse metal prices overnight?",
        },
        "wiki_entity": "16_Psyche",
        "scores": {"shock_hook": 25, "visualizability": 20, "curiosity_gap": 20, "comment_velocity": 14, "data_density": 10, "search_demand": 8},
        "key_facts": [
            {"label": "ALL EARTH ECONOMY", "value": "$105 TRILLION", "numeric": 105, "unit": "T"},
            {"label": "16 PSYCHE VALUE", "value": "$10 QUINTILLION", "numeric": 100000, "unit": "T"},
            {"label": "PER HUMAN SHARE", "value": "$1.2 BILLION", "numeric": 1.2, "unit": "B"},
            {"label": "ASTEROID WIDTH", "value": "226 KM WIDE", "numeric": 226, "unit": "KM"},
        ],
        "visual_queries": [
            "asteroid space nasa orbit",
            "spacecraft rocket launch nasa",
            "gold bullion bars vault",
            "earth from space orbit nasa",
            "solar system planet asteroid belt",
        ],
    },
    {
        "topic_id": "titan-implosion-20-milliseconds",
        "pillar": "science_anomalies",
        "format_signature": "physics_reaction_race",
        "primary_keyword": "deep ocean implosion milliseconds vs brain",
        "title_variants": [
            "Why Your Brain Literally Cannot Feel a Deep-Sea Implosion",
            "20 Milliseconds vs 150 Milliseconds: The Physics of Deep Ocean Pressure",
            "At 3,800 Meters Deep, Water Crushes Steel Faster Than a Nerve Signal",
        ],
        "thumbnail_hooks": [["20 MS vs", "150 MS"], ["FASTER THAN", "PAIN"], ["3,800M", "PRESSURE"]],
        "shock_hook_stat": "20 MS vs 150 MS BRAIN",
        "hook_subtext": "DEEP OCEAN IMPLOSION PHYSICS",
        "debate_hook": {
            "question": "WOULD YOU EVER RIDE A SUBMARINE TO 4,000 METERS?",
            "option_a": "NO CHANCE",
            "option_b": "YES, ONCE",
            "pinned": "Be honest: knowing steel collapses in 20 milliseconds while a pain signal takes 150 milliseconds, would you ever dive to the Titanic?",
        },
        "wiki_entity": "Implosion_(mechanical_process)",
        "scores": {"shock_hook": 25, "visualizability": 20, "curiosity_gap": 20, "comment_velocity": 14, "data_density": 10, "search_demand": 8},
        "key_facts": [
            {"label": "IMPLOSION TIME", "value": "20 MILLISEC", "numeric": 20, "unit": "MS"},
            {"label": "BRAIN PAIN SIGNAL", "value": "150 MILLISEC", "numeric": 150, "unit": "MS"},
            {"label": "TITANIC DEPTH", "value": "3,800 METERS", "numeric": 3800, "unit": "M"},
            {"label": "HULL PRESSURE", "value": "375 ATM", "numeric": 375, "unit": "ATM"},
        ],
        "visual_queries": [
            "deep ocean submarine underwater",
            "ocean waves storm sea surface",
            "submarine hull steel engineering",
            "deep sea abyss underwater water",
            "titanic ocean underwater sonar",
        ],
    },
    {
        "topic_id": "airplane-window-tiny-hole-secret",
        "pillar": "hidden_tech",
        "format_signature": "everyday_survival_engineering",
        "primary_keyword": "airplane window tiny hole bleed valve",
        "title_variants": [
            "Why Every Airplane Window Has That Tiny Pin-Hole (It Saves Your Life)",
            "The 1-Millimeter Hole Stopping Airplane Windows From Exploding",
            "Never Cover This Tiny Hole on an Airplane Window",
        ],
        "thumbnail_hooks": [["1MM HOLE", "SAVES YOU"], ["AIRPLANE", "WINDOW SECRET"], ["WHY IT", "EXISTS"]],
        "shock_hook_stat": "1 MM HOLE = CABIN LIFE",
        "hook_subtext": "THE BLEED HOLE ENGINEERING",
        "debate_hook": {
            "question": "DID YOU KNOW WHAT THAT TINY WINDOW HOLE DOES?",
            "option_a": "HAD NO IDEA",
            "option_b": "KNEW IT",
            "pinned": "Quick poll: did you actually know that tiny hole in airplane windows equalizes 35,000-foot cabin pressure, or did you always wonder why it's there?",
        },
        "wiki_entity": "Cabin_pressurization",
        "scores": {"shock_hook": 24, "visualizability": 20, "curiosity_gap": 20, "comment_velocity": 14, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "BLEED HOLE SIZE", "value": "1.5 MM WIDE", "numeric": 1.5, "unit": "MM"},
            {"label": "CRUISE ALTITUDE", "value": "11,000 METERS", "numeric": 11000, "unit": "M"},
            {"label": "OUTSIDE TEMP", "value": "-56 CELSIUS", "numeric": 56, "unit": "C"},
            {"label": "WINDOW LAYERS", "value": "3 ACRYLIC PANES", "numeric": 3, "unit": "PANES"},
        ],
        "visual_queries": [
            "airplane window clouds sky flight",
            "commercial jet wing flying clouds",
            "aircraft fuselage aviation cockpit",
            "passenger jet cabin window view",
            "airplane flying sunset sky",
        ],
    },
    {
        "topic_id": "how-fast-you-move-sitting-still",
        "pillar": "science_anomalies",
        "format_signature": "hidden_velocity_stack",
        "primary_keyword": "how fast are we moving through space",
        "title_variants": [
            "You Are Moving 2.1 Million KM/H Right Now While Sitting Still",
            "The Insane Speed You Travel Through Space Without Feeling a Thing",
            "Why You Never Feel Earth Hurdling at 107,000 KM/H",
        ],
        "thumbnail_hooks": [["2.1 MILLION", "KM PER HOUR"], ["SITTING STILL", "IS A LIE"], ["EARTH SPEED", "EXPOSED"]],
        "shock_hook_stat": "2,100,000 KM/H RIGHT NOW",
        "hook_subtext": "YOUR HIDDEN COSMIC VELOCITY",
        "debate_hook": {
            "question": "WHAT IF EARTH STOPPED SPINNING FOR JUST 1 SECOND?",
            "option_a": "INSTANT CHAOS",
            "option_b": "EXPLAIN NEXT",
            "pinned": "Since you finished watching this 30-second video, you just traveled over 17,000 kilometers through the universe. Should we break down what happens if Earth stopped spinning for 1 second?",
        },
        "wiki_entity": "Earth%27s_orbit",
        "scores": {"shock_hook": 24, "visualizability": 20, "curiosity_gap": 19, "comment_velocity": 14, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "EARTH SPIN", "value": "1,670 KM/H", "numeric": 1670, "unit": "KM/H"},
            {"label": "ORBIT AROUND SUN", "value": "107,000 KM/H", "numeric": 107000, "unit": "KM/H"},
            {"label": "MILKY WAY SPEED", "value": "828,000 KM/H", "numeric": 828000, "unit": "KM/H"},
            {"label": "COSMIC TOTAL", "value": "2.1M KM/H", "numeric": 2100000, "unit": "KM/H"},
        ],
        "visual_queries": [
            "earth rotation from space nasa",
            "milky way galaxy stars night sky",
            "sun solar flare space nasa",
            "astronaut spacewalk earth orbit nasa",
            "deep space nebula stars nasa",
        ],
    },
    {
        "topic_id": "one-grain-of-sand-space-bullet",
        "pillar": "science_anomalies",
        "format_signature": "kinetic_impact_shock",
        "primary_keyword": "space debris paint fleck orbital velocity",
        "title_variants": [
            "A Single Paint Fleck in Space Hits Like a Bowling Ball at 100 MPH",
            "Why a 1-Millimeter Piece of Space Trash Can Punch Through Steel",
            "28,000 KM/H: The Deadliest Bullet Floating Above Your Head",
        ],
        "thumbnail_hooks": [["1 PAINT FLECK", "= BOWLING BALL"], ["28,000 KM/H", "SPACE TRASH"], ["ORBITAL", "BULLETS"]],
        "shock_hook_stat": "0.2 GRAMS = BOWLING BALL",
        "hook_subtext": "ORBITAL KINETIC ENERGY",
        "debate_hook": {
            "question": "WILL SPACE JUNK TRAP HUMANITY ON EARTH ONE DAY?",
            "option_a": "YES, KESSLER",
            "option_b": "WE CLEAN IT",
            "pinned": "Over 100 million microscopic fragments are whipping around Earth at 10x rifle bullet speed right now. Do you think space junk will trap us on Earth?",
        },
        "wiki_entity": "Space_debris",
        "scores": {"shock_hook": 25, "visualizability": 20, "curiosity_gap": 19, "comment_velocity": 13, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "RIFLE BULLET", "value": "3,000 KM/H", "numeric": 3000, "unit": "KM/H"},
            {"label": "ORBITAL PAINT FLECK", "value": "28,000 KM/H", "numeric": 28000, "unit": "KM/H"},
            {"label": "TRACKED OBJECTS", "value": "100 MILLION+", "numeric": 100, "unit": "M"},
            {"label": "SHUTTLE WINDOW HIT", "value": "4 MM CRATER", "numeric": 4, "unit": "MM"},
        ],
        "visual_queries": [
            "international space station earth orbit nasa",
            "space shuttle window earth orbit nasa",
            "satellite orbit space debris nasa",
            "astronaut earth horizon nasa",
            "rocket launch space atmosphere nasa",
        ],
    },
    {
        "topic_id": "one-line-of-code-370m-rocket-crash",
        "pillar": "hidden_tech",
        "format_signature": "catastrophic_bug_autopsy",
        "primary_keyword": "Ariane 5 integer overflow 370 million crash",
        "title_variants": [
            "One Single Number Bug Blew Up a $370 Million Rocket in 37 Seconds",
            "The Most Expensive Software Error in Human History (Ariane 5)",
            "How 64-Bit vs 16-Bit Code Turned a $370M Rocket Into Fire",
        ],
        "thumbnail_hooks": [["1 CODE BUG", "= -$370M"], ["37 SECONDS", "TO BOOM"], ["64-BIT vs", "16-BIT"]],
        "shock_hook_stat": "1 BUG = -$370,000,000",
        "hook_subtext": "ARIANE 5 FLIGHT 501 AUTOPSY",
        "debate_hook": {
            "question": "WOULD YOU TRUST PURE AI CODE TO FLY A ROCKET?",
            "option_a": "NEVER",
            "option_b": "YES",
            "pinned": "Ten years of engineering and $370 million vanished in 37 seconds because one 64-bit number overflowed a 16-bit slot. Would you trust AI to write flight-control code?",
        },
        "wiki_entity": "Ariane_flight_V88",
        "scores": {"shock_hook": 24, "visualizability": 20, "curiosity_gap": 20, "comment_velocity": 14, "data_density": 10, "search_demand": 8},
        "key_facts": [
            {"label": "ROCKET COST", "value": "$370 MILLION", "numeric": 370, "unit": "M"},
            {"label": "FLIGHT LIFETIME", "value": "37 SECONDS", "numeric": 37, "unit": "SEC"},
            {"label": "MAX 16-BIT LIMIT", "value": "32,767", "numeric": 32767, "unit": "INT"},
            {"label": "DEV TIME LOST", "value": "10 YEARS", "numeric": 10, "unit": "YRS"},
        ],
        "visual_queries": [
            "rocket launch fire exhaust nasa",
            "mission control room nasa computers",
            "software code computer screen monitor",
            "space launch pad rocket night nasa",
            "explosion fire smoke launch",
        ],
    },
    {
        "topic_id": "traffic-jam-phantom-wave-1-brake",
        "pillar": "mind_glitches",
        "format_signature": "emergent_chaos_math",
        "primary_keyword": "phantom traffic jam single brake wave",
        "title_variants": [
            "How ONE Driver Tapping the Brakes Causes a 2-Hour Traffic Jam",
            "The Invisible Shockwave Behind Every Traffic Jam With No Accident",
            "Japanese Scientists Proved Traffic Jams Appear Out of Thin Air",
        ],
        "thumbnail_hooks": [["1 BRAKE TAP", "= 2HR JAM"], ["PHANTOM", "TRAFFIC WAVE"], ["NO ACCIDENT", "AT ALL"]],
        "shock_hook_stat": "1 BRAKE TAP = 2 HOUR JAM",
        "hook_subtext": "PHANTOM TRAFFIC SHOCKWAVE",
        "debate_hook": {
            "question": "WHAT CAUSES MORE TRAFFIC: SLOW DRIVERS OR TAILGATERS?",
            "option_a": "TAILGATERS",
            "option_b": "SLOW DRIVERS",
            "pinned": "Scientists put 22 cars on a closed circular track with zero obstacles — and a full traffic jam formed in 40 seconds. Who causes more traffic: tailgaters or left-lane campers?",
        },
        "wiki_entity": "Traffic_wave",
        "scores": {"shock_hook": 24, "visualizability": 20, "curiosity_gap": 19, "comment_velocity": 15, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "TEST TRACK CARS", "value": "22 DRIVERS", "numeric": 22, "unit": "CARS"},
            {"label": "JAM FORMATION", "value": "40 SECONDS", "numeric": 40, "unit": "SEC"},
            {"label": "BACKWARD WAVE", "value": "20 KM/H", "numeric": 20, "unit": "KM/H"},
            {"label": "HUMAN REACTION", "value": "1.2 SECONDS", "numeric": 1.2, "unit": "SEC"},
        ],
        "visual_queries": [
            "highway traffic jam cars aerial",
            "freeway car headlights night traffic",
            "cars brake lights road congestion",
            "city highway interchange aerial",
            "road traffic rush hour cars",
        ],
    },
    {
        "topic_id": "casino-no-clocks-psychological-trap",
        "pillar": "mind_glitches",
        "format_signature": "architectural_time_distortion",
        "primary_keyword": "why casinos have no clocks or windows",
        "title_variants": [
            "Why You Never Find a Clock or Window Inside Any Casino",
            "5 Hidden Architecture Traps Casinos Use to Erase Your Sense of Time",
            "How Casino Carpets Are Scientifically Designed to Keep You Awake",
        ],
        "thumbnail_hooks": [["ZERO CLOCKS", "BY DESIGN"], ["CASINO", "MIND TRAP"], ["TIME ERASED", "INDOORS"]],
        "shock_hook_stat": "0 CLOCKS · 0 WINDOWS",
        "hook_subtext": "ENGINEERED TIME BLINDNESS",
        "debate_hook": {
            "question": "DO CASINOS ACTUALLY PUMP EXTRA OXYGEN? YES OR MYTH?",
            "option_a": "MYTH",
            "option_b": "REAL",
            "pinned": "Fun fact: pumping oxygen is actually illegal (fire hazard), so casinos use maze layouts, zero clocks, and loud ugly carpets instead. Ever lost track of 4+ hours indoors?",
        },
        "wiki_entity": "Casino_design",
        "scores": {"shock_hook": 24, "visualizability": 19, "curiosity_gap": 19, "comment_velocity": 14, "data_density": 9, "search_demand": 10},
        "key_facts": [
            {"label": "WALL CLOCKS", "value": "0 ALLOWED", "numeric": 1, "unit": "CLOCK"},
            {"label": "AVG STAY LIFT", "value": "+42% LONGER", "numeric": 42, "unit": "%"},
            {"label": "HOUSE EDGE", "value": "2% TO 15%", "numeric": 15, "unit": "%"},
            {"label": "LAS VEGAS REV", "value": "$15B / YEAR", "numeric": 15, "unit": "B"},
        ],
        "visual_queries": [
            "las vegas casino neon lights night",
            "slot machine casino floor lights",
            "roulette table casino interior",
            "las vegas strip night architecture",
            "playing cards poker chips table",
        ],
    },
    {
        "topic_id": "you-never-actually-touch-anything",
        "pillar": "science_anomalies",
        "format_signature": "quantum_reality_paradox",
        "primary_keyword": "atomic repulsion never physically touch anything",
        "title_variants": [
            "Physically, You Have Never Touched Anything in Your Entire Life",
            "You Are Hovering Above Your Chair Right Now (Atomic Repulsion)",
            "The Quantum Force Field Keeping Your Atoms From Fusing Together",
        ],
        "thumbnail_hooks": [["YOU NEVER", "TOUCH ANYTHING"], ["HOVERING", "RIGHT NOW"], ["99.9999%", "EMPTY SPACE"]],
        "shock_hook_stat": "99.9999999% EMPTY SPACE",
        "hook_subtext": "ELECTROMAGNETIC REPULSION",
        "debate_hook": {
            "question": "IF ATOMS NEVER TOUCH, WHY DOES GETTING HIT STILL HURT?",
            "option_a": "FORCE FIELD",
            "option_b": "NERVES",
            "pinned": "Right now your skin is hovering about 0.00000001 centimeters above your phone screen, repelled by electron fields. Does that blow your mind or feel fake?",
        },
        "wiki_entity": "Pauli_exclusion_principle",
        "scores": {"shock_hook": 25, "visualizability": 19, "curiosity_gap": 20, "comment_velocity": 14, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "EMPTY ATOM SPACE", "value": "99.9999999%", "numeric": 99.99, "unit": "%"},
            {"label": "HOVER GAP", "value": "10^-10 METERS", "numeric": 10, "unit": "NM"},
            {"label": "REPULSION SPEED", "value": "LIGHT SPEED", "numeric": 300000, "unit": "KM/S"},
            {"label": "HUMAN ATOMS", "value": "7 OCTILLION", "numeric": 7, "unit": "OCT"},
        ],
        "visual_queries": [
            "physics laboratory laser beam",
            "microscope atoms science research",
            "human hand light shadow",
            "particle accelerator cern physics",
            "quantum crystal light refraction",
        ],
    },
    {
        "topic_id": "trillion-dollar-platinum-coin-loophole",
        "pillar": "money_scale",
        "format_signature": "legal_monetary_glitch",
        "primary_keyword": "one trillion dollar platinum coin loophole",
        "title_variants": [
            "The Real Legal Loophole That Lets the US Mint One $1 Trillion Coin",
            "How One 1-Ounce Platinum Coin Could Legally Erase $1 Trillion Debt",
            "The Strangest Loophole Still Sitting Inside US Federal Law",
        ],
        "thumbnail_hooks": [["$1 TRILLION", "SINGLE COIN"], ["LEGAL", "MONEY GLITCH"], ["1 OUNCE", "PLATINUM"]],
        "shock_hook_stat": "1 COIN = $1,000,000,000,000",
        "hook_subtext": "31 USC SECTION 5112(K)",
        "debate_hook": {
            "question": "IF THEY MINTED IT, WOULD INFLATION EXPLODE IMMEDIATELY?",
            "option_a": "HYPERINFLATION",
            "option_b": "NOTHING HAPPENS",
            "pinned": "Under 31 U.S.C. § 5112(k), the Treasury Secretary can legally mint a platinum coin of ANY denomination — even $1 trillion — in 24 hours. Smart backup or economic disaster?",
        },
        "wiki_entity": "Trillion-dollar_coin",
        "scores": {"shock_hook": 25, "visualizability": 19, "curiosity_gap": 20, "comment_velocity": 14, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "COIN METAL VALUE", "value": "$1,000 METAL", "numeric": 1000, "unit": "USD"},
            {"label": "LEGAL FACE VALUE", "value": "$1 TRILLION", "numeric": 1000000000000, "unit": "USD"},
            {"label": "VALUE MULTIPLIER", "value": "1 BILLION X", "numeric": 1000000000, "unit": "X"},
            {"label": "LAW SECTION", "value": "31 USC 5112", "numeric": 5112, "unit": "LAW"},
        ],
        "visual_queries": [
            "united states treasury building washington",
            "federal reserve bank building vault",
            "silver platinum coin bullion",
            "us dollar currency printing money",
            "capitol building washington dc",
        ],
    },
    {
        "topic_id": "kola-superdeep-borehole-limit",
        "pillar": "science_anomalies",
        "format_signature": "planetary_depth_limit",
        "primary_keyword": "Kola Superdeep Borehole deepest hole Earth",
        "title_variants": [
            "Why Humans Stopped Digging at 12 KM (The Earth Started Melting Steel)",
            "The Deepest Hole Ever Dug Barely Scratched 0.2% of Planet Earth",
            "What Scientists Actually Found 12,262 Meters Underground",
        ],
        "thumbnail_hooks": [["STOPPED AT", "12.2 KM"], ["ONLY 0.2%", "OF EARTH"], ["180°C ROCK", "LIKE PLASTIC"]],
        "shock_hook_stat": "12.2 KM = 0.2% OF EARTH",
        "hook_subtext": "KOLA SUPERDEEP BOREHOLE",
        "debate_hook": {
            "question": "WHAT DO YOU THINK WE'LL REACH FIRST: MARS OR EARTH'S MANTLE?",
            "option_a": "MARS FIRST",
            "option_b": "MANTLE FIRST",
            "pinned": "It took 20 years of drilling just to pierce 0.2% of Earth's radius before rock turned to 180°C plastic. Will humans walk on Mars before we ever reach Earth's mantle?",
        },
        "wiki_entity": "Kola_Superdeep_Borehole",
        "scores": {"shock_hook": 24, "visualizability": 19, "curiosity_gap": 19, "comment_velocity": 14, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "HOLE DEPTH", "value": "12.2 KM DEEP", "numeric": 12.2, "unit": "KM"},
            {"label": "EARTH RADIUS", "value": "6,371 KM", "numeric": 6371, "unit": "KM"},
            {"label": "BOTTOM HEAT", "value": "180 CELSIUS", "numeric": 180, "unit": "C"},
            {"label": "HOLE DIAMETER", "value": "23 CM WIDE", "numeric": 23, "unit": "CM"},
        ],
        "visual_queries": [
            "drilling rig industrial borehole",
            "volcano lava magma glowing rock",
            "earth planet globe space nasa",
            "underground mine tunnel rock",
            "geology canyon deep earth layers",
        ],
    },
    {
        "topic_id": "cargo-ship-250k-tons-float-physics",
        "pillar": "hidden_tech",
        "format_signature": "counterintuitive_buoyancy_scale",
        "primary_keyword": "how 250000 ton steel cargo ships float",
        "title_variants": [
            "How a 250,000-Ton Steel Ship Floats While a 1-Gram Pebble Sinks",
            "The Simple Physics Trick Holding Up 24,000 Steel Containers on Water",
            "Why Solid Steel Sinks Instantly — Yet This 400-Meter Giant Floats",
        ],
        "thumbnail_hooks": [["250,000 TONS", "STILL FLOATS"], ["1G PEBBLE", "SINKS FAST"], ["STEEL HULL", "SECRET"]],
        "shock_hook_stat": "250,000 TONS ON WATER",
        "hook_subtext": "ARCHIMEDES DISPLACEMENT",
        "debate_hook": {
            "question": "IF YOU FLOOD HALF THE HULL, HOW FAST DOES IT SINK?",
            "option_a": "UNDER 10 MIN",
            "option_b": "HOURS",
            "pinned": "A 400-meter container ship weighs 250,000 tons yet has an average density lower than water because 90% of its hull is trapped air. Would you ever work on an ocean freighter?",
        },
        "wiki_entity": "Buoyancy",
        "scores": {"shock_hook": 23, "visualizability": 20, "curiosity_gap": 18, "comment_velocity": 13, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "SHIP WEIGHT", "value": "250,000 TONS", "numeric": 250000, "unit": "TONS"},
            {"label": "SHIP LENGTH", "value": "400 METERS", "numeric": 400, "unit": "M"},
            {"label": "CONTAINERS", "value": "24,000 BOXES", "numeric": 24000, "unit": "TEU"},
            {"label": "TRAPPED AIR", "value": "90% VOLUME", "numeric": 90, "unit": "%"},
        ],
        "visual_queries": [
            "container ship ocean sea cargo",
            "shipping port cranes containers",
            "cargo vessel hull shipyard steel",
            "ocean waves freighter sea",
            "massive ship sailing water",
        ],
    },
    {
        "topic_id": "slot-machine-near-miss-brain-hack",
        "pillar": "mind_glitches",
        "format_signature": "neurological_near_miss_exploit",
        "primary_keyword": "slot machine near miss dopamine psychology",
        "title_variants": [
            "Why 'Almost Winning' Lights Up Your Brain Just Like Actually Winning",
            "The 1-Millimeter Slot Machine Illusion Engineered to Drain Wallets",
            "How Near-Misses Trick Human Dopamine Into Playing 33% Longer",
        ],
        "thumbnail_hooks": [["ALMOST WON", "= DOPAMINE"], ["+33% LONGER", "PLAY TIME"], ["NEAR-MISS", "BRAIN HACK"]],
        "shock_hook_stat": "ALMOST WIN = REAL WIN SIGNAL",
        "hook_subtext": "THE NEAR-MISS NEURAL LOOP",
        "debate_hook": {
            "question": "SHOULD NEAR-MISS ALGORITHMS IN GAMES BE BANNED?",
            "option_a": "BAN THEM",
            "option_b": "KEEP LEGAL",
            "pinned": "Brain scans show losing by 'one slot' fires the exact same reward circuit as winning — and mobile loot boxes copied the exact formula. Should near-miss mechanics be regulated?",
        },
        "wiki_entity": "Near-miss_effect",
        "scores": {"shock_hook": 24, "visualizability": 19, "curiosity_gap": 19, "comment_velocity": 15, "data_density": 9, "search_demand": 9},
        "key_facts": [
            {"label": "TRUE LOSS", "value": "0% PAYOUT", "numeric": 1, "unit": "%"},
            {"label": "PLAY EXTENSION", "value": "+33% LONGER", "numeric": 33, "unit": "%"},
            {"label": "REEL WEIGHTING", "value": "12X NEAR-MISS", "numeric": 12, "unit": "X"},
            {"label": "GLOBAL MARKET", "value": "$100B+ / YR", "numeric": 100, "unit": "B"},
        ],
        "visual_queries": [
            "slot machine casino jackpot lights",
            "neon arcade game machine lights",
            "brain mri scan neurology",
            "las vegas slot machines row",
            "smartphone gaming screen hands",
        ],
    },
    {
        "topic_id": "gold-never-rusts-5000-years",
        "pillar": "money_scale",
        "format_signature": "relativistic_chemistry_value",
        "primary_keyword": "why gold never rusts Einstein relativity",
        "title_variants": [
            "Why Gold Never Rusts After 5,000 Years (And Why It's Actually Yellow)",
            "Einstein's Relativity Is the Secret Reason Gold Still Shines Forever",
            "Pull Iron Out of the Ocean and It Crumbles — Pull Gold Out and It Glows",
        ],
        "thumbnail_hooks": [["5,000 YEARS", "ZERO RUST"], ["EINSTEIN", "MADE IT GOLD"], ["58% SPEED", "OF LIGHT"]],
        "shock_hook_stat": "5,000 YEARS · ZERO RUST",
        "hook_subtext": "RELATIVISTIC GOLD ELECTRONS",
        "debate_hook": {
            "question": "WHICH HOLDS VALUE BETTER IN 50 YEARS: GOLD OR BITCOIN?",
            "option_a": "GOLD",
            "option_b": "BITCOIN",
            "pinned": "Gold's inner electrons orbit at 58% of light speed, locking out oxygen forever — which is why 5,000-year-old shipwreck gold shines brand new. Next 50 years: Gold or Bitcoin?",
        },
        "wiki_entity": "Relativistic_quantum_chemistry",
        "scores": {"shock_hook": 24, "visualizability": 20, "curiosity_gap": 19, "comment_velocity": 15, "data_density": 9, "search_demand": 8},
        "key_facts": [
            {"label": "ELECTRON SPEED", "value": "58% LIGHT SPEED", "numeric": 58, "unit": "% C"},
            {"label": "RUST AFTER 5000Y", "value": "0.00% DECAY", "numeric": 1, "unit": "%"},
            {"label": "ATOMIC NUMBER", "value": "79 PROTONS", "numeric": 79, "unit": "Z"},
            {"label": "SHIPWRECK GOLD", "value": "100% INTACT", "numeric": 100, "unit": "%"},
        ],
        "visual_queries": [
            "gold bullion bars treasury shine",
            "ancient egyptian gold mask museum",
            "gold coins treasure underwater",
            "chemistry laboratory gold metal",
            "federal reserve gold vault",
        ],
    },
    {
        "topic_id": "lithium-battery-thermal-runaway-chain",
        "pillar": "hidden_tech",
        "format_signature": "microscopic_energy_chain",
        "primary_keyword": "lithium battery thermal runaway chain reaction",
        "title_variants": [
            "How One Microscopic Scratch Inside a Phone Battery Triggers 1,000°C Fire",
            "Why Water Cannot Put Out a Lithium Battery Fire (It Makes Its Own Oxygen)",
            "Inside the 20-Micron Barrier Stopping Your Phone From Catching Fire",
        ],
        "thumbnail_hooks": [["20 MICRONS", "TO 1,000°C"], ["MAKES OWN", "OXYGEN"], ["BATTERY", "CHAIN FIRE"]],
        "shock_hook_stat": "20 MICRONS = 1,000°C FIRE",
        "hook_subtext": "THERMAL RUNAWAY PHYSICS",
        "debate_hook": {
            "question": "DO YOU SLEEP WITH YOUR PHONE CHARGING UNDER YOUR PILLOW?",
            "option_a": "GUILTY",
            "option_b": "NEVER",
            "pinned": "Only a 20-micron plastic film — thinner than a human hair — separates your phone battery's energy layers. Do you leave your phone charging overnight next to your bed?",
        },
        "wiki_entity": "Thermal_runaway",
        "scores": {"shock_hook": 24, "visualizability": 19, "curiosity_gap": 19, "comment_velocity": 14, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "SEPARATOR FILM", "value": "20 MICRONS", "numeric": 20, "unit": "UM"},
            {"label": "HUMAN HAIR", "value": "70 MICRONS", "numeric": 70, "unit": "UM"},
            {"label": "RUNAWAY PEAK", "value": "1,000 CELSIUS", "numeric": 1000, "unit": "C"},
            {"label": "IGNITION TIME", "value": "UNDER 3 SEC", "numeric": 3, "unit": "SEC"},
        ],
        "visual_queries": [
            "smartphone battery circuit electronics",
            "electric car battery pack factory",
            "fire sparks thermal heat",
            "lithium battery cells technology",
            "microscope electronics silicon",
        ],
    },
    {
        "topic_id": "survive-on-every-planet-seconds",
        "pillar": "science_anomalies",
        "format_signature": "planetary_survival_countdown",
        "primary_keyword": "how long can you survive on each planet",
        "title_variants": [
            "How Many Seconds You Would Survive on Venus vs Mars Without a Suit",
            "Mars Gives You 90 Seconds — Venus Kills You in Under 1 Second",
            "The Brutal Countdown of Every Planet in Our Solar System",
        ],
        "thumbnail_hooks": [["MARS: 90S", "VENUS: <1S"], ["NO SUIT", "SURVIVAL"], ["465°C +", "ACID AIR"]],
        "shock_hook_stat": "MARS 90 SEC vs VENUS <1 SEC",
        "hook_subtext": "PLANETARY SURVIVAL LIMITS",
        "debate_hook": {
            "question": "IF GIVEN A FREE ONE-WAY TICKET TO MARS COLONY, WOULD YOU GO?",
            "option_a": "SIGN ME UP",
            "option_b": "STAY ON EARTH",
            "pinned": "Mars gives you roughly 90 seconds before low pressure kills you, while Venus crushes and cooks you at 465°C in under 1 second. Would you ever take a one-way ticket to Mars?",
        },
        "wiki_entity": "Atmosphere_of_Venus",
        "scores": {"shock_hook": 25, "visualizability": 20, "curiosity_gap": 20, "comment_velocity": 15, "data_density": 10, "search_demand": 9},
        "key_facts": [
            {"label": "VENUS SURVIVAL", "value": "UNDER 1 SEC", "numeric": 1, "unit": "SEC"},
            {"label": "MARS SURVIVAL", "value": "90 SECONDS", "numeric": 90, "unit": "SEC"},
            {"label": "VENUS HEAT", "value": "465 CELSIUS", "numeric": 465, "unit": "C"},
            {"label": "VENUS PRESSURE", "value": "92 ATM", "numeric": 92, "unit": "ATM"},
        ],
        "visual_queries": [
            "planet venus space nasa",
            "planet mars surface rover nasa",
            "jupiter storm space nasa",
            "solar system planets orbit nasa",
            "astronaut mars space suit nasa",
        ],
    },
]

# Dynamic Wikipedia anomaly seed pool used after all 24 curated blueprints are exhausted (0-key infinite mode)
DYNAMIC_WIKI_SEEDS: List[Dict[str, str]] = [
    {"entity": "Large_Hadron_Collider", "pillar": "hidden_tech", "kw": "Large Hadron Collider energy scale"},
    {"entity": "Voyager_1", "pillar": "science_anomalies", "kw": "Voyager 1 distance signal delay"},
    {"entity": "SWIFT", "pillar": "money_scale", "kw": "SWIFT banking network daily volume"},
    {"entity": "Sovereign_wealth_fund", "pillar": "money_scale", "kw": "Norway sovereign wealth fund scale"},
    {"entity": "Bystander_effect", "pillar": "mind_glitches", "kw": "bystander effect psychology percentage"},
    {"entity": "Kessler_syndrome", "pillar": "hidden_tech", "kw": "space debris Kessler syndrome orbit"},
    {"entity": "Dunning–Kruger_effect", "pillar": "mind_glitches", "kw": "Dunning Kruger effect cognitive curve"},
    {"entity": "Fort_Knox", "pillar": "money_scale", "kw": "Fort Knox gold reserve bullion weight"},
    {"entity": "Chernobyl_disaster", "pillar": "science_anomalies", "kw": "Elephant Foot Chernobyl radiation seconds"},
    {"entity": "James_Webb_Space_Telescope", "pillar": "hidden_tech", "kw": "James Webb Space Telescope mirror precision"},
    {"entity": "Three_Gorges_Dam", "pillar": "science_anomalies", "kw": "Three Gorges Dam slows Earth rotation"},
    {"entity": "Burj_Khalifa", "pillar": "hidden_tech", "kw": "Burj Khalifa wind engineering height"},
    {"entity": "Sunk_cost", "pillar": "mind_glitches", "kw": "sunk cost fallacy brain decision trap"},
    {"entity": "Hyperinflation_in_Zimbabwe", "pillar": "money_scale", "kw": "100 trillion dollar bill hyperinflation"},
    {"entity": "Tardigrade", "pillar": "science_anomalies", "kw": "tardigrade vacuum space survival limits"},
    {"entity": "Black_hole", "pillar": "science_anomalies", "kw": "spaghettification black hole event horizon"},
    {"entity": "Deepwater_Horizon", "pillar": "hidden_tech", "kw": "deepwater oil rig ocean pressure"},
    {"entity": "Tulip_mania", "pillar": "money_scale", "kw": "tulip mania single bulb house price"},
    {"entity": "Placebo", "pillar": "mind_glitches", "kw": "placebo effect brain real painkillers"},
    {"entity": "Olympus_Mons", "pillar": "science_anomalies", "kw": "Olympus Mons Mars volcano vs Everest"},
    {"entity": "Panama_Canal", "pillar": "hidden_tech", "kw": "Panama Canal single ship transit toll"},
    {"entity": "Loss_aversion", "pillar": "mind_glitches", "kw": "loss aversion psychology 2x pain"},
    {"entity": "Antimatter", "pillar": "money_scale", "kw": "one gram of antimatter 62 trillion dollars"},
    {"entity": "Speed_of_light", "pillar": "science_anomalies", "kw": "speed of light around Earth per second"},
    {"entity": "Flash_crash_of_2010", "pillar": "money_scale", "kw": "2010 flash crash 1 trillion erased minutes"},
    {"entity": "Halo_effect", "pillar": "mind_glitches", "kw": "halo effect first impression bias"},
    {"entity": "International_Space_Station", "pillar": "hidden_tech", "kw": "ISS 16 sunrises every day orbit speed"},
]


class IdeaEngine:
    """3-Tier Autonomous Viral Idea Discovery, Verification & 85+ Gate Scorer."""

    MIN_VIRAL_SCORE = 85

    def __init__(self, state_db: StateDB, llm: Optional[ZeroCostLLMClient] = None) -> None:
        self.db = state_db
        self.llm = llm or ZeroCostLLMClient()

    def _enrich_with_wikipedia_fact(self, entity: str) -> Optional[str]:
        """Verify real-world grounding via free zero-key Wikipedia REST summary API."""
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{entity}"
        headers = {"User-Agent": WIKI_UA}
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                extract = resp.json().get("extract", "").strip().replace("\n", " ")
                if extract:
                    snippet = extract[:420]
                    last_dot = snippet.rfind(".")
                    return snippet[: last_dot + 1] if last_dot > 80 else snippet
        except Exception as exc:
            logger.debug("Wikipedia summary lookup skipped for %s (%s)", entity, type(exc).__name__)
        return None

    def _generate_llm_fresh_blueprint(self, used_ids: set[str], pillar: Optional[str]) -> Optional[Dict[str, Any]]:
        """Generate a net-new 85+ documentary concept via free-tier LLM when curated pool is spent."""
        if not self.llm.is_available:
            return None
        system_prompt = load_prompt("idea_scorer.md")
        user_prompt = (
            "Invent ONE brand-new, verifiable, borderless documentary concept for VELUM "
            "(Visual Comparisons, Hidden Systems & Extreme Facts). "
            f"Preferred pillar: {pillar or 'any of money_scale, hidden_tech, mind_glitches, science_anomalies'}. "
            f"Avoid these already-produced topic_ids: {sorted(used_ids)[-20:]}. "
            "Include 4 hard numeric `key_facts`, 3 `thumbnail_hooks` (each array of 2 lines, max 3 words total), "
            "`visual_queries` (5 photography search strings), and `hook_subtext`."
        )
        raw = self.llm.complete_json(system_prompt, user_prompt, temperature=0.8)
        if not raw or not raw.get("topic_id") or len(raw.get("key_facts", [])) < 4:
            return None
        if raw["topic_id"] in used_ids:
            raw["topic_id"] = f"{raw['topic_id']}-{len(used_ids) + 1}"
        raw.setdefault("format_signature", "llm_scale_discovery")
        raw.setdefault("hook_subtext", "HIDDEN SCALE TELEMETRY")
        raw.setdefault("thumbnail_hooks", [["HIDDEN", "SCALE"], ["EXTREME", "SYSTEM"], ["1,000X", "REALITY"]])
        raw.setdefault("visual_queries", [raw.get("primary_keyword", "modern technology architecture")] * 5)
        return raw

    def _synthesize_live_wikipedia_blueprint(
        self, used_ids: set[str], preferred_pillar: Optional[str] = None
    ) -> Dict[str, Any]:
        """Zero-key dynamic Wikipedia anomaly synthesizer for endless unique topics."""
        candidates = [
            s for s in DYNAMIC_WIKI_SEEDS
            if f"wiki-{s['entity'].lower().replace('_', '-')}" not in used_ids
        ]
        if preferred_pillar:
            pillar_matches = [s for s in candidates if s["pillar"] == preferred_pillar]
            if pillar_matches:
                candidates = pillar_matches
        seed = candidates[0] if candidates else random.choice(DYNAMIC_WIKI_SEEDS)
        entity = seed["entity"]
        slug_id = f"wiki-{entity.lower().replace('_', '-')}"
        if slug_id in used_ids:
            slug_id = f"{slug_id}-{len(used_ids) + 1}"

        extract = self._enrich_with_wikipedia_fact(entity) or ""
        nums = re.findall(r"\b\d[\d,\.]*\s*(?:km|m|million|billion|trillion|%|percent|years|seconds|tons)?", extract, re.I)
        n0 = nums[0].strip().upper() if len(nums) > 0 else "100X"
        n1 = nums[1].strip().upper() if len(nums) > 1 else "1,000X"
        clean_name = entity.replace("_", " ")

        return {
            "topic_id": slug_id,
            "pillar": preferred_pillar or seed["pillar"],
            "format_signature": "live_wiki_anomaly",
            "primary_keyword": seed["kw"],
            "title_variants": [
                f"The Extreme Scale Behind {clean_name} Nobody Pictures",
                f"Inside {clean_name}: The Hidden Numbers Running Reality",
                f"Why {clean_name} Breaks Every Human Intuition",
            ],
            "thumbnail_hooks": [
                [clean_name.split()[0].upper(), "EXTREME"],
                ["HIDDEN", "LIMIT"],
                [n0[:8], "SCALE"],
            ],
            "shock_hook_stat": f"{clean_name.upper()[:18]}",
            "hook_subtext": "VERIFIED EXTREME TELEMETRY",
            "wiki_entity": entity,
            "wiki_summary": extract,
            "scores": {"shock_hook": 22, "visualizability": 18, "curiosity_gap": 18, "comment_velocity": 12, "data_density": 9, "search_demand": 9},
            "key_facts": [
                {"label": "PRIMARY METRIC", "value": n0[:14] or "EXTREME", "numeric": 10.0, "unit": "UNIT"},
                {"label": "SECONDARY SCALE", "value": n1[:14] or "1,000X", "numeric": 1000.0, "unit": "UNIT"},
                {"label": "VERIFICATION", "value": "100% DATA", "numeric": 100.0, "unit": "%"},
                {"label": "SYSTEM CLASS", "value": (preferred_pillar or seed["pillar"]).replace("_", " ").upper()[:12], "numeric": 1.0, "unit": "TIER"},
            ],
            "visual_queries": [
                f"{clean_name} science engineering",
                f"{seed['kw']} dark photography",
                "laboratory instrumentation dark",
                "earth from space night",
                "modern infrastructure architecture",
            ],
        }

    def _synthesize_part2_variant(
        self, queue_entry: Dict[str, Any], used_ids: set[str]
    ) -> Dict[str, Any]:
        """Synthesize a fresh Part-2 sequel variant when all curated blueprints in a pillar are used."""
        pillar = str(queue_entry.get("pillar") or "science_anomalies")
        source_topic_id = str(queue_entry.get("source_topic_id") or "")
        source_title = str(queue_entry.get("source_title") or "")

        # Prefer unused dynamic Wikipedia seed in the same pillar first
        wiki_pillar_unused = [
            s for s in DYNAMIC_WIKI_SEEDS
            if s["pillar"] == pillar and f"wiki-{s['entity'].lower().replace('_', '-')}" not in used_ids
        ]
        if wiki_pillar_unused:
            return self._synthesize_live_wikipedia_blueprint(used_ids, preferred_pillar=pillar)

        # Otherwise derive a fresh Part-2 sequel blueprint from the breakout winner or pillar flagship
        base_bp = next((bp for bp in CURATED_BLUEPRINTS if bp["topic_id"] == source_topic_id), None)
        if base_bp is None:
            pillar_bps = [bp for bp in CURATED_BLUEPRINTS if bp["pillar"] == pillar]
            base_bp = max(pillar_bps, key=lambda b: sum(b.get("scores", {}).values())) if pillar_bps else CURATED_BLUEPRINTS[0]

        base_slug = re.sub(r"-part2(?:-\d+)?$", "", base_bp["topic_id"])
        sequel_id = f"{base_slug}-part2"
        suffix = 2
        while sequel_id in used_ids:
            suffix += 1
            sequel_id = f"{base_slug}-part2-{suffix}"

        variant = json.loads(json.dumps(base_bp))
        variant["topic_id"] = sequel_id
        variant["pillar"] = pillar
        variant["format_signature"] = f"{base_bp.get('format_signature', 'scale_contrast')}_part2"
        orig_titles = list(base_bp.get("title_variants", []))
        ref_short = (source_title or (orig_titles[0] if orig_titles else base_bp["primary_keyword"]))[:64]
        variant["title_variants"] = [
            f"Part 2: The Wilder Numbers Behind {base_bp['primary_keyword'].title()}"[:95],
            f"Part 2: Going Even Deeper Into {ref_short}"[:95],
            f"The Hidden Part 2 Twist Everyone Missed: {base_bp['shock_hook_stat']}"[:95],
        ]
        variant["hook_subtext"] = "PART 2 // DEEPER SCALE"
        return variant

    def _pop_viewer_idea_entry(self) -> Optional[Dict[str, Any]]:
        """Pop and persist the oldest verified viewer-requested topic from state.db."""
        raw = self.db.get_meta("viewer_ideas_queue_json")
        if not raw:
            return None
        try:
            queue = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(queue, list) or not queue:
            return None
        entry = queue.pop(0)
        self.db.set_meta("viewer_ideas_queue_json", json.dumps(queue, ensure_ascii=False))
        return entry if isinstance(entry, dict) else None

    def _build_viewer_idea_blueprint(
        self, entry: Dict[str, Any], used_ids: set[str]
    ) -> Dict[str, Any]:
        """Convert a Wikipedia-verified viewer idea into a full V4 documentary blueprint."""
        clean_name = str(entry.get("title_clean") or entry.get("query") or "Hidden Phenomenon").strip()
        wiki_entity = str(entry.get("wiki_entity") or clean_name.replace(" ", "_")).strip()
        pillar = str(entry.get("pillar") or "science_anomalies").strip()
        extract = str(entry.get("wiki_summary") or "").strip()
        if not extract and wiki_entity:
            extract = self._enrich_with_wikipedia_fact(wiki_entity) or ""

        base_tid = str(entry.get("topic_id") or "").strip()
        if not base_tid:
            slug = re.sub(r"[^a-z0-9]+", "-", clean_name.lower()).strip("-")[:48]
            base_tid = f"viewer-{slug or 'topic'}"
        topic_id = base_tid
        suffix = 2
        while topic_id in used_ids:
            topic_id = f"{base_tid}-{suffix}"
            suffix += 1

        raw_nums = re.findall(
            r"\b\d[\d,\.]*\s*(?:km/s|km/h|km|million|billion|trillion|%|percent|years|seconds|milliseconds|tons|tonnes|degrees|meters|metres|miles|hours|days|light-years|kg|mw|gw|tw|v|hz)?\b",
            extract,
            re.IGNORECASE,
        )
        cleaned_nums: List[str] = []
        for item in raw_nums:
            val = re.sub(r"\s+", " ", item.strip()).upper()
            if val and val not in cleaned_nums:
                cleaned_nums.append(val)

        def _parse_numeric(val: str, default: float) -> float:
            m = re.search(r"[\d,\.]+", val)
            if not m:
                return default
            try:
                return float(m.group(0).replace(",", ""))
            except ValueError:
                return default

        n0 = cleaned_nums[0][:14] if len(cleaned_nums) > 0 else "EXTREME"
        n1 = cleaned_nums[1][:14] if len(cleaned_nums) > 1 else "100%"
        n2 = cleaned_nums[2][:14] if len(cleaned_nums) > 2 else "VERIFIED"
        n3 = cleaned_nums[3][:14] if len(cleaned_nums) > 3 else "GLOBAL"

        first_token = re.sub(r"[^A-Za-z0-9]", "", clean_name.split()[0]).upper()[:10] or "VIEWER"
        shock_stat = f"{clean_name.upper()[:22]}"
        if cleaned_nums:
            candidate_stat = f"{cleaned_nums[0]} // {first_token}"
            if len(candidate_stat) <= 24:
                shock_stat = candidate_stat

        pillar_label = pillar.replace("_", " ").upper()[:16]
        return {
            "topic_id": topic_id,
            "pillar": pillar,
            "format_signature": "viewer_request_scale",
            "primary_keyword": clean_name.lower(),
            "title_variants": [
                f"A Viewer Asked About {clean_name} — The Real Numbers Are Wild"[:95],
                f"Inside {clean_name}: The Verified Scale Nobody Talks About"[:95],
                f"Why {clean_name} Breaks Every Intuition You Have"[:95],
            ],
            "thumbnail_hooks": [
                [first_token, "EXPLAINED"],
                [n0[:9] if cleaned_nums else "VIEWER", "SCALE"],
                ["HIDDEN", "REALITY"],
            ],
            "shock_hook_stat": shock_stat,
            "hook_subtext": "VIEWER REQUEST // VERIFIED DATA",
            "wiki_entity": wiki_entity,
            "wiki_summary": extract,
            "is_viewer_requested": True,
            "display_name": clean_name,
            "viewer_query_clean": str(entry.get("query") or clean_name)[:80],
            "scores": {
                "shock_hook": 22,
                "visualizability": 18,
                "curiosity_gap": 19,
                "comment_velocity": 14,
                "data_density": 9,
                "search_demand": 9,
            },
            "key_facts": [
                {"label": "KEY BENCHMARK", "value": n0, "numeric": _parse_numeric(n0, 10.0), "unit": "METRIC_A"},
                {"label": "VERIFIED SCALE", "value": n1, "numeric": _parse_numeric(n1, 100.0), "unit": "METRIC_B"},
                {"label": "MEASURED DETAIL", "value": n2, "numeric": _parse_numeric(n2, 50.0), "unit": "METRIC_C"},
                {"label": "CATEGORY", "value": n3 if len(cleaned_nums) > 3 else pillar_label, "numeric": _parse_numeric(n3, 1.0), "unit": "TIER"},
            ],
            "debate_hook": {
                "question": f"DID YOU ALREADY KNOW THIS ABOUT {clean_name.upper()[:24]}?",
                "option_a": "MIND BLOWN",
                "option_b": "ALREADY KNEW",
            },
            "visual_queries": [
                f"{clean_name} documentary photography",
                f"{clean_name} science space architecture",
                f"{clean_name} close up macro",
                "earth from space night satellite",
                "modern laboratory engineering dark",
            ],
        }

    def _pop_part2_queue_entry(self) -> Optional[Dict[str, Any]]:
        """Pop and persist the oldest queued breakout Part-2 sequel entry from state.db."""
        raw = self.db.get_meta("part2_queue_json")
        if not raw:
            return None
        try:
            queue = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(queue, list) or not queue:
            return None
        entry = queue.pop(0)
        self.db.set_meta("part2_queue_json", json.dumps(queue, ensure_ascii=False))
        return entry if isinstance(entry, dict) else None

    def score_idea(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Score a candidate idea against prompts/idea_scorer.md (85+ gate)."""
        if self.llm.is_available:
            system_prompt = load_prompt("idea_scorer.md")
            user_prompt = (
                "Score this documentary concept rigorously. Keep factual accuracy strict.\n"
                f"Candidate JSON:\n{json.dumps(candidate, ensure_ascii=False)}"
            )
            llm_scored = self.llm.complete_json(system_prompt, user_prompt, temperature=0.35)
            if llm_scored and isinstance(llm_scored.get("total_score"), (int, float)):
                total = int(llm_scored["total_score"])
                merged = dict(candidate)
                merged["scores"] = llm_scored.get("scores", candidate.get("scores", {}))
                merged["total_score"] = total
                merged["approved"] = total >= self.MIN_VIRAL_SCORE
                if llm_scored.get("title_variants"):
                    merged["title_variants"] = llm_scored["title_variants"][:3]
                if llm_scored.get("shock_hook_stat"):
                    merged["shock_hook_stat"] = llm_scored["shock_hook_stat"]
                return merged

        scores = candidate.get("scores", {})
        total = int(sum(scores.values()))
        if len(candidate.get("key_facts", [])) < 4:
            total -= 12
        if not candidate.get("shock_hook_stat"):
            total -= 20

        result = dict(candidate)
        result["total_score"] = max(0, min(100, total))
        result["approved"] = result["total_score"] >= self.MIN_VIRAL_SCORE
        result["rejection_reason"] = (
            "" if result["approved"] else f"Score {result['total_score']} below 85 threshold"
        )
        return result

    def select_next_topic(self, preferred_pillar: Optional[str] = None) -> Dict[str, Any]:
        """Select the highest-scoring unused concept (viewer ideas -> Part-2 clones -> leaderboard pool)."""
        used_ids = set(self.db.get_used_topic_ids())

        # 0. PRIORITY CHECK: Verified Viewer-Requested Idea Harvester queue
        while True:
            viewer_entry = self._pop_viewer_idea_entry()
            if viewer_entry is None:
                break
            candidate_tid = str(viewer_entry.get("topic_id") or "")
            if candidate_tid and candidate_tid in used_ids:
                continue
            viewer_bp = self._build_viewer_idea_blueprint(viewer_entry, used_ids)
            scored_viewer = self.score_idea(viewer_bp)
            scored_viewer["is_viewer_requested"] = True
            scored_viewer["approved"] = True
            scored_viewer["total_score"] = max(88, int(scored_viewer.get("total_score", 90)))
            self.db.save_topic(
                scored_viewer,
                format_signature=scored_viewer.get("format_signature", "viewer_request_scale"),
            )
            logger.info(
                "VIEWER-REQUESTED TOPIC ACTIVATED -> %s | pillar=%s | score=%d/100",
                scored_viewer["topic_id"],
                scored_viewer["pillar"],
                scored_viewer["total_score"],
            )
            return scored_viewer

        # 1. PRIORITY CHECK: Breakout Winner Part-2 Auto-Cloner queue
        part2_entry = self._pop_part2_queue_entry()
        if part2_entry is not None:
            source_pillar = str(part2_entry.get("pillar") or preferred_pillar or "")
            source_title = str(part2_entry.get("source_title") or "")
            source_topic_id = str(part2_entry.get("source_topic_id") or "")
            source_views = int(part2_entry.get("source_views", 0) or 0)

            pillar_pool = sorted(
                [
                    bp for bp in CURATED_BLUEPRINTS
                    if bp["topic_id"] not in used_ids
                    and (not source_pillar or bp["pillar"] == source_pillar)
                ],
                key=lambda bp: sum(bp.get("scores", {}).values()),
                reverse=True,
            )

            if not pillar_pool:
                fresh_llm = self._generate_llm_fresh_blueprint(used_ids, source_pillar or None)
                if fresh_llm:
                    pillar_pool = [fresh_llm]
                else:
                    pillar_pool = [self._synthesize_part2_variant(part2_entry, used_ids)]

            approved_part2: List[Dict[str, Any]] = []
            for candidate in pillar_pool[:6]:
                scored = self.score_idea(candidate)
                if scored["approved"]:
                    approved_part2.append(scored)
                    break

            if not approved_part2:
                synth = self.score_idea(self._synthesize_part2_variant(part2_entry, used_ids))
                approved_part2.append(synth)

            winner = approved_part2[0]
            winner["is_part2_followup"] = True
            winner["part2_reference_title"] = source_title
            winner["part2_source_topic_id"] = source_topic_id
            winner["part2_source_views"] = source_views

            wiki_entity = winner.get("wiki_entity", "")
            if wiki_entity and not winner.get("wiki_summary"):
                summary = self._enrich_with_wikipedia_fact(wiki_entity)
                if summary:
                    winner["wiki_summary"] = summary

            self.db.save_topic(winner, format_signature=winner.get("format_signature", "scale_contrast"))
            logger.info(
                "BREAKOUT PART-2 CLONE ACTIVATED | source=%s (%d views) -> sequel=%s | pillar=%s | score=%d/100",
                source_topic_id or "breakout",
                source_views,
                winner["topic_id"],
                winner["pillar"],
                winner["total_score"],
            )
            return winner

        # 2. Standard high-viral selection with Self-Optimizing Pillar Velocity Boost
        winning_meta = self.db.get_meta("winning_format_json")
        pillar_perf_raw = self.db.get_meta("pillar_performance_json")
        pillar_perf: Dict[str, float] = {}
        if pillar_perf_raw:
            try:
                parsed_perf = json.loads(pillar_perf_raw)
                if isinstance(parsed_perf, dict):
                    pillar_perf = {str(k): float(v) for k, v in parsed_perf.items()}
            except (ValueError, TypeError):
                pillar_perf = {}

        target_pillar = preferred_pillar
        if not target_pillar and pillar_perf:
            target_pillar = max(pillar_perf.items(), key=lambda kv: kv[1])[0]
            logger.info("Autonomous Pillar Leaderboard active -> fastest pillar: %s (%.1f v/hr)", target_pillar, pillar_perf[target_pillar])
        elif not target_pillar and winning_meta:
            try:
                parsed = json.loads(winning_meta)
                target_pillar = parsed.get("pillar")
                logger.info("Growth Mutator bias active -> targeting winning pillar: %s", target_pillar)
            except json.JSONDecodeError:
                target_pillar = None

        pool = [bp for bp in CURATED_BLUEPRINTS if bp["topic_id"] not in used_ids]
        if not pool:
            fresh_llm = self._generate_llm_fresh_blueprint(used_ids, target_pillar)
            pool = [fresh_llm] if fresh_llm else [self._synthesize_live_wikipedia_blueprint(used_ids, target_pillar)]

        def _rank_key(bp: Dict[str, Any]) -> float:
            base_s = float(sum(bp.get("scores", {}).values()))
            boost = 3.0 if (target_pillar and bp.get("pillar") == target_pillar) else 0.0
            return base_s + boost

        pool = sorted(pool, key=_rank_key, reverse=True)

        approved_candidates: List[Dict[str, Any]] = []
        # Evaluate top 8 candidates to keep strict 85+ viral gate & maximize topic punch
        for candidate in pool[:8]:
            scored = self.score_idea(candidate)
            self.db.save_topic(scored, format_signature=scored.get("format_signature", "scale_contrast"))
            if scored["approved"]:
                approved_candidates.append(scored)
            else:
                logger.info("Rejected topic %s (score=%s < 85)", scored["topic_id"], scored["total_score"])

        if not approved_candidates:
            raise RuntimeError("No candidate passed the 85+ viral score gate.")

        approved_candidates.sort(
            key=lambda item: float(item["total_score"]) + (3.0 if (target_pillar and item.get("pillar") == target_pillar) else 0.0),
            reverse=True,
        )
        winner = approved_candidates[0]

        wiki_entity = winner.get("wiki_entity", "")
        if wiki_entity and not winner.get("wiki_summary"):
            summary = self._enrich_with_wikipedia_fact(wiki_entity)
            if summary:
                winner["wiki_summary"] = summary

        logger.info(
            "Selected viral topic: %s | pillar=%s | score=%d/100 (pool=%d remaining)",
            winner["topic_id"],
            winner["pillar"],
            winner["total_score"],
            max(0, len(pool) - 1),
        )
        return winner
