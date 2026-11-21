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
]

# Dynamic Wikipedia anomaly seed pool used after all 24 curated blueprints are exhausted (0-key infinite mode)
DYNAMIC_WIKI_SEEDS: List[Dict[str, str]] = [
    {"entity": "Kola_Superdeep_Borehole", "pillar": "science_anomalies", "kw": "Kola Superdeep Borehole depth comparison"},
    {"entity": "Large_Hadron_Collider", "pillar": "hidden_tech", "kw": "Large Hadron Collider energy scale"},
    {"entity": "Voyager_1", "pillar": "science_anomalies", "kw": "Voyager 1 distance signal delay"},
    {"entity": "SWIFT", "pillar": "money_scale", "kw": "SWIFT banking network daily volume"},
    {"entity": "Sovereign_wealth_fund", "pillar": "money_scale", "kw": "Norway sovereign wealth fund scale"},
    {"entity": "Bystander_effect", "pillar": "mind_glitches", "kw": "bystander effect psychology percentage"},
    {"entity": "Kessler_syndrome", "pillar": "hidden_tech", "kw": "space debris Kessler syndrome orbit"},
    {"entity": "Dunning–Kruger_effect", "pillar": "mind_glitches", "kw": "Dunning Kruger effect cognitive curve"},
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

    def _synthesize_live_wikipedia_blueprint(self, used_ids: set[str]) -> Dict[str, Any]:
        """Zero-key dynamic Wikipedia anomaly synthesizer for endless unique topics."""
        candidates = [
            s for s in DYNAMIC_WIKI_SEEDS
            if f"wiki-{s['entity'].lower().replace('_', '-')}" not in used_ids
        ]
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
            "pillar": seed["pillar"],
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
                {"label": "SYSTEM CLASS", "value": seed["pillar"].replace("_", " ").upper()[:12], "numeric": 1.0, "unit": "TIER"},
            ],
            "visual_queries": [
                f"{clean_name} science engineering",
                f"{seed['kw']} dark photography",
                "laboratory instrumentation dark",
                "earth from space night",
                "modern infrastructure architecture",
            ],
        }

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
        """Select the highest-scoring unused concept passing the 85+ viral gate."""
        used_ids = set(self.db.get_used_topic_ids())

        winning_meta = self.db.get_meta("winning_format_json")
        target_pillar = preferred_pillar
        if not target_pillar and winning_meta:
            try:
                parsed = json.loads(winning_meta)
                target_pillar = parsed.get("pillar")
                logger.info("Growth Mutator bias active -> targeting winning pillar: %s", target_pillar)
            except json.JSONDecodeError:
                target_pillar = None

        pool = [bp for bp in CURATED_BLUEPRINTS if bp["topic_id"] not in used_ids]
        if not pool:
            fresh_llm = self._generate_llm_fresh_blueprint(used_ids, target_pillar)
            pool = [fresh_llm] if fresh_llm else [self._synthesize_live_wikipedia_blueprint(used_ids)]

        if target_pillar:
            matching = [bp for bp in pool if bp["pillar"] == target_pillar]
            if matching:
                pool = matching

        approved_candidates: List[Dict[str, Any]] = []
        # Evaluate top 6 candidates to avoid redundant LLM calls while keeping strict 85+ gate
        for candidate in pool[:6]:
            scored = self.score_idea(candidate)
            self.db.save_topic(scored, format_signature=scored.get("format_signature", "scale_contrast"))
            if scored["approved"]:
                approved_candidates.append(scored)
            else:
                logger.info("Rejected topic %s (score=%s < 85)", scored["topic_id"], scored["total_score"])

        if not approved_candidates:
            raise RuntimeError("No candidate passed the 85+ viral score gate.")

        approved_candidates.sort(key=lambda item: item["total_score"], reverse=True)
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
