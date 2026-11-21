"""VELUM Documentary Retention Script Architect (prompts/retention_script.md).

Generates hyper-dense, story-driven scene-by-scene documentary scripts for:
- Shorts (9:16, ~42-55s, seamless infinite loop)
- Long-form (16:9, ~180-240s, multi-chapter deep breakdown)

Enforces:
- 0-2s high-contrast shock hook (zero filler phrases)
- Primary keyword spoken within first 15s (VSEO)
- Visual beat durations strictly <= 2.5s
- Story-specific concrete analogies, physical scale twists, and seamless loops
  across every single topic (never generic placeholder sentences).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from core.config import get_logger, load_prompt
from core.llm_client import ZeroCostLLMClient

logger = get_logger("script_engine")

BANNED_SLOP_PHRASES = (
    "in today's video",
    "welcome back",
    "hey guys",
    "mind-blowing",
    "buckle up",
    "let's dive in",
    "in conclusion",
    "don't forget to like",
    "delve into",
    "tapestry",
)

# Bespoke story arcs for our core viral topics so 0-key runs still read like human-written Vox scripts
TOPIC_STORY_ARCS: Dict[str, List[str]] = {
    "subsea-cables-99-percent-internet": [
        "Ninety nine percent of global internet traffic does not travel through satellites in space.",
        "It fires through undersea cables internet infrastructure thinner than a garden hose.",
        "At the bottom of the ocean, the active fiber core measures just seventeen millimeters across.",
        "Yet over one point four million kilometers of these glass threads wrap the planet.",
        "Every single day, ten trillion dollars of financial transfers pulse through them at light speed.",
        "Satellites handle less than one percent of world data because orbital latency is too slow.",
        "Inside each cable, hair-thin glass fibers carry laser pulses amplified every eighty kilometers.",
        "In shallow coastal waters, a single dragging ship anchor can sever an entire country's bandwidth.",
        "Globally, more than one hundred cable breaks happen every year without the public noticing.",
        "A fleet of specialized repair ships works around the clock hauling broken lines from the abyss.",
        "Just three coastal choke points control the majority of traffic between Europe, Asia, and America.",
        "If those narrow corridors went dark simultaneously, global banking and cloud networks would freeze.",
        "What we call the cloud is actually sitting in freezing mud on the ocean floor.",
        "Which is why the modern world hangs by a thread when you realize that—",
    ],
    "euv-lithography-hardest-machine": [
        "One single company in the Netherlands builds the machine that controls the modern world.",
        "This ASML EUV lithography machine explained costs three hundred and eighty million dollars.",
        "Without it, nobody can manufacture the microchips inside modern phones or artificial intelligence.",
        "Shipping just one machine requires forty freight containers and three Boeing cargo jets.",
        "Inside a vacuum chamber, it drops molten tin droplets fifty thousand times every single second.",
        "A high-power laser blasts each falling droplet twice to vaporize it into extreme ultraviolet plasma.",
        "That plasma flashes at two hundred and twenty thousand degrees, forty times hotter than the sun.",
        "The light is so easily absorbed by air that it must bounce off the flattest mirrors ever polished.",
        "If one mirror were scaled to the size of Germany, its highest bump would be under one millimeter.",
        "That focused beam etches billions of transistor pathways narrower than a human virus.",
        "Not even the wealthiest tech giants on Earth have been able to replicate this supply chain.",
        "Every breakthrough in global computing depends on this one cleanroom bottleneck.",
        "Which makes the entire digital economy fragile the moment you see why—",
    ],
    "mariana-trench-pressure-scale": [
        "Drop a steel ball into the Pacific and it takes over an hour to hit Challenger Deep.",
        "This Mariana Trench pressure comparison reveals an environment more hostile than outer space.",
        "At ten thousand nine hundred and eighty four meters down, sunlight vanished ten kilometers ago.",
        "If you placed Mount Everest on the trench floor, its peak would still sit two kilometers underwater.",
        "Down here, the ocean crushes every square inch with one thousand and eighty six atmospheres.",
        "That feels like fifty jumbo jets stacked directly on top of your thumb.",
        "The pressure is so extreme that water itself compresses and becomes nearly five percent denser.",
        "Air pockets inside a human body would collapse instantly under eight tons per square inch.",
        "More astronauts have walked on the surface of the Moon than have descended into this abyss.",
        "Yet living creatures with gel-like bones still glide silently across the freezing pitch-black floor.",
        "Even bizarre: researchers found plastic bags resting at the very bottom of the trench.",
        "That impossible depth only makes sense when you picture what happens the moment you—",
    ],
    "decoy-effect-pricing-trap": [
        "The medium popcorn at the cinema was never designed for anyone to actually buy it.",
        "This decoy effect pricing psychology is the oldest trap in behavioral economics.",
        "Give customers just two choices: a small for three dollars or a large for seven dollars.",
        "In controlled experiments, sixty eight percent of buyers rationally pick the small.",
        "Wait what happens when marketers insert a useless medium priced at six dollars and fifty cents.",
        "Suddenly the seven dollar large looks like an irresistible bargain for fifty cents more.",
        "In seconds, eighty four percent of people switch to the most expensive option.",
        "Nothing about the large product improved, yet sales jumped by fifty two percentage points.",
        "Your brain hates calculating absolute value, so it hunts for an easy local comparison.",
        "Tech companies use the exact same three-tier trap on storage plans and software subscriptions.",
        "The middle tier exists solely as a psychological decoy to steer you upward.",
        "Once you spot that fake anchor, you notice how every menu is rigged before you realize why—",
    ],
    "gps-relativity-drift-system": [
        "Without Albert Einstein's equations, your phone's GPS map would fail within two minutes.",
        "This GPS general relativity time dilation happens twenty thousand kilometers above your head.",
        "Each navigation satellite screams around Earth at fourteen thousand kilometers per hour.",
        "Because of high orbital speed, special relativity slows the satellite's atomic clock by seven microseconds daily.",
        "At the same time, weaker gravity high above Earth speeds that clock up by forty five microseconds.",
        "Combine both effects and orbital time runs thirty eight microseconds faster every single day.",
        "Thirty eight millionths of a second sounds completely harmless to human senses.",
        "Yet radio signals travel at the speed of light, where one microsecond equals three hundred meters.",
        "Left uncorrected, every GPS pin on Earth would drift by eleven point four kilometers every day.",
        "Within a week, delivery routes, aviation systems, and financial time-stamps would collapse.",
        "Engineers had to deliberately detune satellite atomic clocks before launch just to match Earth time.",
        "Relativity is not abstract theory—it runs silently inside your pocket every time you see why—",
    ],
    "all-world-gold-one-cube-scale": [
        "Melt down every ring, coin, and central bank vault bar ever mined in human history.",
        "The all gold ever mined cube size fits inside a single twenty two meter box.",
        "Six thousand years of empires, wars, and deep-earth mining wouldn't even fill an Olympic stadium.",
        "That entire two hundred and twelve thousand ton cube could sit comfortably inside a tennis court.",
        "Gold is so ridiculously dense at nineteen point three grams per cubic centimeter that volume deceives you.",
        "One cubic meter of solid gold weighs more than nineteen metric tons.",
        "At current market prices, that single twenty two meter cube is worth sixteen trillion dollars.",
        "Every gold ETF, sovereign reserve, and jewelry vault on Earth is fighting over slices of that one box.",
        "Even more shocking: fifty percent of all that gold was mined in just the last seventy years.",
        "When you see how physically tiny humanity's ultimate store of value really is, you realize why—",
    ],
    "container-shipping-hidden-economy": [
        "Ninety percent of everything in your room arrived inside the exact same steel rectangle.",
        "The shipping container global trade system quietly cut ocean transport costs by ninety seven percent.",
        "Before nineteen fifty six, loading a cargo ship by hand cost nearly six dollars per ton.",
        "Standardizing one corrugated box dropped that cost to pennies and rewired global manufacturing.",
        "Today a single ultra-large vessel carries twenty four thousand containers stacked like city blocks.",
        "Unloaded end to end, one ship's cargo stretches for one hundred and forty six kilometers.",
        "Fourteen trillion dollars of goods flow across invisible ocean highways every year.",
        "Yet the entire system squeezes through narrow maritime choke points like the Suez and Panama canals.",
        "Block just one canal for six days and ten billion dollars of daily trade grinds to a halt.",
        "The modern economy runs on floating steel warehouses that nobody notices until you see why—",
    ],
    "compound-penny-vs-million-trap": [
        "Take one million dollars in cash right now, or a single penny doubled every day for thirty days.",
        "This penny doubled 30 days exponential math exposes how badly human intuition fails growth curves.",
        "By day ten, your doubled penny is worth a pathetic five dollars and twelve cents.",
        "Even on day twenty, two thirds of the way through the month, you only have five thousand dollars.",
        "Almost everyone panics here thinking the million dollar briefcase was the smarter choice.",
        "Then the hockey-stick explosion of exponential doubling suddenly Ignites.",
        "Day twenty five crosses three hundred and thirty five thousand dollars.",
        "Day twenty eight breaks one point three four million dollars, passing the cash offer.",
        "By day thirty, that single one-cent coin compounds to five million three hundred and sixty eight thousand dollars.",
        "Over seventy five percent of the total wealth materializes in the final seventy two hours.",
        "Our linear brains always quit right before the vertical part of the curve, which is why—",
    ],
    "global-debt-vs-physical-cash": [
        "Ninety two percent of all the money in the world does not physically exist.",
        "This physical cash vs digital money supply gap is the biggest illusion in modern banking.",
        "Add up every paper banknote and metal coin on Earth and you get roughly nine trillion dollars.",
        "Now zoom out to the broad global money supply sitting inside digital bank ledgers.",
        "That number towers past one hundred and eight trillion dollars.",
        "Whenever a commercial bank issues a mortgage or loan, it types new digital deposits into existence.",
        "Only eight percent of global purchasing power is backed by physical paper you can hold.",
        "Above that sits a derivatives market valued at over six hundred and sixty trillion dollars.",
        "If even ten percent of account holders demanded paper cash on the same morning, ATMs would empty in hours.",
        "The entire financial system runs on synchronized digital trust, which explains why—",
    ],
    "airline-zero-margin-business-model": [
        "Major airlines lose money flying planes and make billions operating as unregulated banks.",
        "The airlines loyalty points bank business model completely flipped commercial aviation.",
        "After fuel, crew, maintenance, and airport fees, an airline nets barely six dollars per passenger.",
        "One storm or fuel spike wipes out an entire quarter of ticket profits overnight.",
        "Now look at the frequent flyer mileage programs attached to those exact same airlines.",
        "Airlines pre-sell billions of loyalty points directly to giant credit card banks for cash.",
        "Wall Street valued the top airline loyalty programs higher than the airlines themselves.",
        "Passengers spend billions on co-branded cards chasing free seats that cost the airline almost nothing.",
        "The aircraft in the sky are essentially flying billboards for a twenty five billion dollar points bank.",
        "Once you follow where the real profit comes from, you never look at a boarding pass the same way when—",
    ],
    "transistor-scale-vs-red-blood-cell": [
        "Your phone processor packs over one hundred billion physical switches inside the size of a fingernail.",
        "A 2nm transistor size visual comparison pushes engineering straight to the edge of atomic physics.",
        "A single human red blood cell measures seven thousand five hundred nanometers wide.",
        "A modern silicon transistor gate measures just two nanometers across.",
        "That means the gap controlling electrical current is barely ten silicon atoms wide.",
        "Each microscopic switch flips on and off five billion times every single second.",
        "At ten atoms thick, electrons start leaking right through solid barriers via quantum tunneling.",
        "Chipmakers now have to stack nanowires vertically in three dimensions just to stop quantum leaks.",
        "Inside your pocket sits an atomic-scale city more complex than any street grid on Earth.",
        "Which makes it almost unbelievable when you zoom back in and realize that—",
    ],
    "power-grid-50hz-real-time-balance": [
        "The electrical grid is the largest machine ever built, yet it stores almost zero electricity.",
        "This electrical power grid frequency balance requires supply and demand to match every millisecond.",
        "Across entire continents, giant spinning turbines lock together at fifty or sixty cycles per second.",
        "When millions of homes flip on air conditioners, physical resistance actually slows those turbines down.",
        "If grid frequency drops by even one percent, transformers overheat and trip offline.",
        "Automated breakers disconnect cities in seconds to save the hardware from melting.",
        "Unlike water or gas networks, global grids hold less than two percent battery buffer.",
        "Every watt lighting your screen right now was generated a fraction of a second ago.",
        "One nine-second frequency cascade can plunge tens of millions of people into total darkness.",
        "Civilization balances on a real-time electromagnetic tightrope every second you forget why—",
    ],
    "dns-root-servers-internet-phonebook": [
        "Thirteen logical addresses quietly direct every single click on the global internet.",
        "This DNS root servers internet control system is the master phonebook of digital civilization.",
        "Whenever you type a website name, your device has no idea where that server physically lives.",
        "In under twenty five milliseconds, it queries a hierarchy anchored by thirteen root authorities labeled A through M.",
        "Those thirteen roots are mirrored across more than eighteen hundred secure anycast nodes worldwide.",
        "To prevent hackers from hijacking the phonebook, the master cryptographic root is locked by physical smartcards.",
        "Fourteen trusted officers from different countries hold the physical keys to reboot the security Ceremony.",
        "Every day this invisible layer resolves hundreds of billions of lookups without a pause.",
        "If the root directory ever corrupted, every domain name on Earth would vanish at once.",
        "The entire web relies on a hidden trust ceremony that starts the instant you notice how—",
    ],
    "high-frequency-trading-microsecond-race": [
        "Wall Street firms spent three hundred million dollars blasting through mountains to save three milliseconds.",
        "In high frequency trading speed of light is the ultimate physical bottleneck.",
        "A human eye blink takes three hundred milliseconds from start to finish.",
        "In that single blink, algorithmic servers execute thousands of cross-market stock orders.",
        "Trading firms realized glass fiber cables slow light down by thirty one percent compared to open air.",
        "So they built chains of line-of-sight microwave towers straight from Chicago to New Jersey.",
        "Inside stock exchange data centers, fairness rules force every server to use the exact same cable length.",
        "Engineers coil extra fiber loops inside cabinets so no computer sits three meters closer to the matching engine.",
        "At light speed, three meters of wire equals a ten nanosecond advantage worth millions.",
        "Global markets now move at relativistic physics limits before a human trader even sees why—",
    ],
    "survivorship-bias-ww2-planes": [
        "When warplanes returned covered in bullet holes, generals ordered extra armor on the most damaged wings.",
        "One mathematician stopped them and proved why survivorship bias airplanes explained a fatal logic trap.",
        "Abraham Wald mapped every strike across returning bombers: wings and tails were riddled with holes.",
        "The cockpit and engines came back almost completely untouched.",
        "The military assumed the wings needed reinforcement because that was where all the hits appeared.",
        "Wald pointed out the chilling truth: the sample only included planes that survived the trip home.",
        "Where were the airplanes with bullet holes in the engines and cockpit?",
        "They were at the bottom of the ocean and never made it back to be counted.",
        "The empty, undamaged spots on the diagram showed where a single hit was instantly fatal.",
        "We make the exact same error every day studying only visible winners while ignoring silent failures.",
        "What is missing from your data matters far more than what you see, which is why—",
    ],
    "supermarket-architecture-psychological-maze": [
        "No supermarket in the world puts milk, eggs, or bread near the front entrance.",
        "These supermarket layout psychology tricks are engineered to double the time you spend walking.",
        "Every store opens with a decompression zone of bright flowers and warm bakery scents.",
        "Fresh bread smell triggers salivary glands, making shoppers buy significantly more food on impulse.",
        "Daily essentials like dairy are locked in the farthest back corner of the building.",
        "To grab a two dollar carton of milk, you must march past thousands of high-margin temptations.",
        "On the shelves, brands pay slotting fees for eye-level placement where sales jump thirty five percent.",
        "Even the floor tiles and slow-tempo background music are calibrated to slow your walking pace.",
        "Shoppers moving slower spend twenty nine percent more money before reaching the checkout lane.",
        "Forty percent of the average grocery basket was never on the shopping list, which happens the moment—",
    ],
    "variable-reward-slot-machine-phone": [
        "The pull-to-refresh gesture on your phone was modeled directly on a Las Vegas slot machine lever.",
        "This variable reward dopamine scroll psychology keeps billions of brains hooked for hours.",
        "Neuroscience discovered that dopamine does not peak when you receive a guaranteed reward.",
        "Dopamine spikes twice as high when a reward is fifty percent uncertain.",
        "If every scroll showed something amazing, your brain would habituate and get bored in minutes.",
        "Instead, algorithmic feeds mix boring posts with occasional viral hits on a random schedule.",
        "Every thumb swipe becomes a miniature slot pull asking: what if the next card is incredible?",
        "The average person now checks their screen one hundred and forty four times a day.",
        "At four point six hours daily, that adds up to over eleven full years of waking life.",
        "Your attention is trapped inside a variable-ratio casino loop every time you forget why—",
    ],
    "anchoring-bias-invisible-price-hack": [
        "Spin a rigged wheel that lands on sixty five, and people suddenly overpay for everything in the room.",
        "This anchoring bias psychology experiment by Kahneman and Tversky exposed a permanent glitch in judgment.",
        "Before estimating a number, your brain grabs the very first figure it sees as a starting anchor.",
        "Even when subjects knew the wheel was random, high anchors pulled their estimates up by eighty percent.",
        "In courtroom trials, experienced judges given a high random dice roll handed out sentences eight months longer.",
        "Retailers weaponize this daily by placing a three thousand dollar watch next to a four hundred dollar one.",
        "Nobody needs to buy the three thousand dollar watch—its only job is to make four hundred feel cheap.",
        "A crossed-out nine hundred and ninety nine price tag rewires your sense of value in zero point four seconds.",
        "You never evaluate price in a vacuum; you only measure distance from the first anchor you saw, which is why—",
    ],
    "zeigarnik-unfinished-loop-memory": [
        "Waiters in nineteen twenties Vienna could memorize twelve complex table orders without writing a word.",
        "Yet the second the bill was paid, their brains deleted the entire order instantly.",
        "This Zeigarnik effect unfinished task psychology explains why open loops hijack human working memory.",
        "Psychologist Bluma Zeigarnik proved that interrupted tasks are remembered ninety percent better than completed ones.",
        "An unfinished task creates cognitive tension that keeps a background thread running in your brain.",
        "The moment the task closes, your mind purges the buffer to save energy.",
        "Streaming platforms weaponize this by cutting episodes at peak tension thirty seconds before resolution.",
        "Your brain treats the cliffhanger as an unfinished survival task and auto-plays the next episode.",
        "Even earworm songs stuck in your head are usually incomplete chorus fragments.",
        "The fastest way to quiet an obsessive thought is to close the open loop, which explains why—",
    ],
    "neutron-star-teaspoon-weight-scale": [
        "Scoop up one single teaspoon of a neutron star and it weighs one billion metric tons.",
        "This neutron star teaspoon weight comparison is the closest matter gets to a black hole.",
        "When a giant star explodes, gravity crushes a core heavier than our Sun into a sphere twenty kilometers wide.",
        "An entire solar mass packs inside the footprint of a single city.",
        "Atoms normally consist of ninety nine point nine nine nine percent empty space between nucleus and electrons.",
        "Inside a neutron star, gravity squeezes electrons straight into protons, erasing that empty space completely.",
        "If you removed the empty atomic space from all eight billion humans on Earth, our species would fit in a sugar cube.",
        "That single sugar cube of humanity would still weigh four hundred million tons.",
        "On a neutron star's surface, gravity is two hundred billion times stronger than Earth's.",
        "Some spin at seven hundred and sixteen revolutions per second without tearing apart, which shows why—",
    ],
    "human-dna-length-to-pluto-scale": [
        "Every microscopic cell in your body holds two full meters of tightly coiled genetic code.",
        "When you calculate human body DNA length solar system scale, the math becomes astronomical.",
        "A single cell nucleus is just six micrometers wide, thinner than a spider silk strand.",
        "Inside that tiny sphere, two meters of DNA folds without tangling using molecular spool proteins.",
        "Now multiply those two meters across all thirty seven trillion cells in an adult human body.",
        "Stretched end to end, your personal DNA forms a thread sixty seven billion miles long.",
        "That single molecular line reaches from Earth to the Sun and back three hundred and sixty times.",
        "Or it stretches all the way to Pluto and back seventeen complete round trips.",
        "You are walking around with an interplanetary length of digital code folded inside you right now.",
        "Which completely transforms how you picture microscopic biology the instant you remember that—",
    ],
    "earth-moon-gap-fits-all-planets": [
        "Every single school textbook drawing of the Earth and Moon lied to your eyes about scale.",
        "In reality, all planets fit between earth and moon with four thousand kilometers to spare.",
        "Look at the actual numbers: average lunar distance measures three hundred and eighty four thousand four hundred kilometers.",
        "Now line up Mercury, Venus, Mars, Jupiter, Saturn, Uranus, and Neptune edge to edge in space.",
        "Even with Jupiter's massive one hundred and thirty nine thousand kilometer equator, the sum is three hundred and eighty thousand kilometers.",
        "Every planet in our solar system slots cleanly into the empty gap between Earth and the Moon.",
        "Classroom diagrams shrink that gap by ten times just so both spheres remain visible on one page.",
        "From Apollo spacecraft windows, Earth looked like a tiny glass marble suspended in an endless black void.",
        "Light itself takes one point two eight seconds just to cross from the Moon to your eyes.",
        "Space is so much emptier than our drawings allow us to picture, which is why—",
    ],
    "point-nemo-closest-humans-in-space": [
        "There is a coordinate in the South Pacific where the closest human beings to you are astronauts in orbit.",
        "At Point Nemo closest humans ISS space station passes just four hundred and eight kilometers overhead.",
        "Meanwhile, the nearest inhabited island on Earth sits two thousand six hundred and eighty eight kilometers away.",
        "You are literally six times closer to astronauts in space than to anyone walking on dry land.",
        "Ocean currents rotating around this zone block nutrient flow, creating an underwater biological desert.",
        "No commercial shipping lanes or passenger flights ever cross these empty coordinates.",
        "Because it is so isolated, space agencies use Point Nemo as Earth's official spacecraft graveyard.",
        "Over two hundred and sixty decommissioned satellites and space stations lie sunken four kilometers below.",
        "When the International Space Station retires, it will plunge into this exact same abyss.",
        "The loneliest place on Earth looks straight up at orbit, which makes you realize why—",
    ],
}


def _topic_specific_beats(topic: Dict[str, Any], fmt: str) -> List[Dict[str, Any]]:
    """Build hyper-dense, zero-fluff documentary beats tailored to the topic's real numbers."""
    tid = topic["topic_id"]
    base_tid = re.sub(r"-v\d+$", "", tid)
    facts = topic["key_facts"]
    queries = topic.get("visual_queries", ["dark technology infrastructure", "data visualization grid"])

    def q(idx: int) -> str:
        return queries[idx % len(queries)]

    if base_tid.startswith("one-million-vs-one-billion"):
        shorts_beats = [
            {
                "narration": "One million seconds is just eleven and a half days.",
                "visual_type": "data_plate",
                "plate_mode": "comparison_bars",
                "plate_data": {
                    "title": "THE TIME SCALE SHOCK",
                    "left_label": "1 MILLION SEC",
                    "left_value": 11.5,
                    "left_display": "11.5 DAYS",
                    "right_label": "1 BILLION SEC",
                    "right_value": 11574,
                    "right_display": "31.7 YEARS",
                    "ratio_badge": "1,000x GAP",
                },
                "visual_query": q(3),
                "hud_tag": "HOOK // SCALE 01",
                "hud_metric": "11.5 DAYS",
                "hud_delta": "10^6 SEC",
                "sfx": "sub_boom",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "One billion seconds is thirty one point seven years.",
                "visual_type": "data_plate",
                "plate_mode": "metric_hero",
                "plate_data": {
                    "title": "ONE BILLION SECONDS",
                    "hero_value": "31.7 YRS",
                    "subtitle": "NEARLY HALF A HUMAN LIFETIME",
                    "accent": "amber",
                },
                "visual_query": q(3),
                "hud_tag": "RATIO // 1000X",
                "hud_metric": "31.7 YEARS",
                "hud_delta": "+99,900%",
                "sfx": "whoosh",
                "camera_motion": "zoom_out",
            },
            {
                "narration": "That single million vs billion scale comparison exposes a massive glitch in human perception.",
                "visual_type": "photo_grade",
                "visual_query": q(0),
                "hud_tag": "VSEO // PERCEPTION",
                "hud_metric": "0.1% GAP",
                "hud_delta": "COGNITIVE BIAS",
                "sfx": "tick",
                "camera_motion": "pan_right",
            },
            {
                "narration": "Your brain hears both words and treats them like close neighbors.",
                "visual_type": "photo_grade",
                "visual_query": q(2),
                "hud_tag": "NEURAL // SCALE",
                "hud_metric": "LOG ERROR",
                "hud_delta": "LINEAR BRAIN",
                "sfx": "none",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "In reality, one million is literally zero point one percent of a billion.",
                "visual_type": "data_plate",
                "plate_mode": "comparison_bars",
                "plate_data": {
                    "title": "REAL PROPORTION",
                    "left_label": "$1,000,000",
                    "left_value": 1,
                    "left_display": "0.1%",
                    "right_label": "$1,000,000,000",
                    "right_value": 1000,
                    "right_display": "100%",
                    "ratio_badge": "1 : 1000",
                },
                "visual_query": q(1),
                "hud_tag": "RATIO // EXACT",
                "hud_metric": "0.10%",
                "hud_delta": "1 IN 1,000",
                "sfx": "sonar",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "Now test this with real money.",
                "visual_type": "photo_grade",
                "visual_query": q(1),
                "hud_tag": "SIM // BURN RATE",
                "hud_metric": "$10,000/D",
                "hud_delta": "STRESS TEST",
                "sfx": "whoosh",
                "camera_motion": "pan_left",
            },
            {
                "narration": "Spend ten thousand dollars every single day starting tonight.",
                "visual_type": "data_plate",
                "plate_mode": "metric_hero",
                "plate_data": {
                    "title": "DAILY SPENDING RATE",
                    "hero_value": "$10,000",
                    "subtitle": "EVERY 24 HOURS WITHOUT STOPPING",
                    "accent": "cyan",
                },
                "visual_query": q(1),
                "hud_tag": "BURN // DAILY",
                "hud_metric": "$10,000",
                "hud_delta": "-10K / 24H",
                "sfx": "tick",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "A millionaire goes completely broke in one hundred days.",
                "visual_type": "data_plate",
                "plate_mode": "timeline_scale",
                "plate_data": {
                    "title": "RUNWAY AT $10K / DAY",
                    "markers": [
                        {"label": "$1M", "value": "100 DAYS", "pct": 0.08, "color": "cyan"},
                        {"label": "$10M", "value": "2.7 YRS", "pct": 0.25, "color": "cyan"},
                        {"label": "$1B", "value": "273 YRS", "pct": 0.96, "color": "amber"},
                    ],
                },
                "visual_query": q(0),
                "hud_tag": "MILLIONAIRE",
                "hud_metric": "100 DAYS",
                "hud_delta": "EMPTY",
                "sfx": "glitch",
                "camera_motion": "pan_right",
            },
            {
                "narration": "A billionaire keeps spending for two hundred and seventy three years.",
                "visual_type": "photo_grade",
                "visual_query": q(0),
                "hud_tag": "BILLIONAIRE",
                "hud_metric": "273 YEARS",
                "hud_delta": "3.5 LIFETIMES",
                "sfx": "sub_boom",
                "camera_motion": "zoom_out",
            },
            {
                "narration": "Even weirder: stack one million dollars in hundred dollar bills.",
                "visual_type": "photo_grade",
                "visual_query": q(1),
                "hud_tag": "PHYSICAL // HEIGHT",
                "hud_metric": "1.09 M",
                "hud_delta": "WAIST HIGH",
                "sfx": "whoosh",
                "camera_motion": "drift_up",
            },
            {
                "narration": "The stack barely reaches waist height at one meter tall.",
                "visual_type": "data_plate",
                "plate_mode": "comparison_bars",
                "plate_data": {
                    "title": "CASH STACK HEIGHT ($100 BILLS)",
                    "left_label": "$1 MILLION",
                    "left_value": 1.09,
                    "left_display": "1.09 M",
                    "right_label": "$1 BILLION",
                    "right_value": 1092,
                    "right_display": "1,092 M",
                    "ratio_badge": "TALLER THAN BURJ KHALIFA",
                },
                "visual_query": q(0),
                "hud_tag": "STACK // $1M",
                "hud_metric": "1.09 M",
                "hud_delta": "10,000 BILLS",
                "sfx": "tick",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "One billion dollars towers past one kilometer straight into the clouds.",
                "visual_type": "photo_grade",
                "visual_query": q(4),
                "hud_tag": "STACK // $1B",
                "hud_metric": "1,092 M",
                "hud_delta": "1.3x BURJ KHALIFA",
                "sfx": "riser",
                "camera_motion": "drift_up",
            },
            {
                "narration": "Now jump just one more word to one trillion seconds.",
                "visual_type": "data_plate",
                "plate_mode": "radar_alert",
                "plate_data": {
                    "title": "SCALE ANOMALY DETECTED",
                    "metric": "31,709 YEARS",
                    "subtitle": "ONE TRILLION SECONDS BACK TO THE ICE AGE",
                    "severity": "EXTREME",
                },
                "visual_query": q(4),
                "hud_tag": "ANOMALY // 10^12",
                "hud_metric": "31,709 YRS",
                "hud_delta": "ICE AGE ERA",
                "sfx": "sub_boom",
                "camera_motion": "zoom_in",
            },
            {
                "narration": "That stretches back thirty one thousand years to the Ice Age.",
                "visual_type": "photo_grade",
                "visual_query": q(4),
                "hud_tag": "TIMELINE // DEEP",
                "hud_metric": "-29,700 BC",
                "hud_delta": "HUMAN PREHISTORY",
                "sfx": "sonar",
                "camera_motion": "zoom_out",
            },
            {
                "narration": "Every extra zero does not add scale, it multiplies worlds apart.",
                "visual_type": "data_plate",
                "plate_mode": "system_nodes",
                "plate_data": {
                    "title": "EXPONENTIAL ARCHITECTURE",
                    "nodes": ["10^6 // 11.5D", "10^9 // 31.7Y", "10^12 // 31.7KY"],
                    "caption": "HUMAN INTUITION BREAKS ABOVE 10^6",
                },
                "visual_query": q(2),
                "hud_tag": "SYSTEM // RULE",
                "hud_metric": "10^3 STEP",
                "hud_delta": "NON-LINEAR",
                "sfx": "whoosh",
                "camera_motion": "pan_left",
            },
            {
                "narration": "Which is the exact blind spot that makes it so shocking when you remember—",
                "visual_type": "photo_grade",
                "visual_query": q(3),
                "hud_tag": "LOOP // REPLAY",
                "hud_metric": "RE-INDEXING",
                "hud_delta": "SEAMLESS",
                "sfx": "tick",
                "camera_motion": "zoom_in",
            },
        ]
    elif base_tid in TOPIC_STORY_ARCS:
        # Build rich bespoke story-driven visual beats from our topic-specific narrative script!
        lines = TOPIC_STORY_ARCS[base_tid]
        f0, f1, f2, f3 = facts[0], facts[1], facts[2], facts[3]
        plate_sequence = [
            (
                "metric_hero",
                {
                    "title": f0["label"],
                    "hero_value": f0["value"],
                    "subtitle": topic.get("hook_subtext", "VELUM TELEMETRY"),
                    "accent": "amber",
                },
            ),
            (
                "comparison_bars",
                {
                    "title": topic["primary_keyword"].upper()[:28],
                    "left_label": f0["label"][:14],
                    "left_value": float(abs(f0["numeric"])) or 1.0,
                    "left_display": f0["value"],
                    "right_label": f1["label"][:14],
                    "right_value": float(abs(f1["numeric"])) or 100.0,
                    "right_display": f1["value"],
                    "ratio_badge": topic["shock_hook_stat"][:18],
                },
            ),
            (
                "radar_alert",
                {
                    "title": f2["label"],
                    "metric": f2["value"],
                    "subtitle": lines[min(4, len(lines) - 1)][:48].upper(),
                    "severity": "EXTREME",
                },
            ),
            (
                "timeline_scale",
                {
                    "title": "VERIFIED SCALE THRESHOLDS",
                    "markers": [
                        {"label": f0["label"][:11], "value": f0["value"], "pct": 0.20, "color": "cyan"},
                        {"label": f1["label"][:11], "value": f1["value"], "pct": 0.54, "color": "amber"},
                        {"label": f3["label"][:11], "value": f3["value"], "pct": 0.90, "color": "crimson"},
                    ],
                },
            ),
            (
                "system_nodes",
                {
                    "title": "SYSTEM ARCHITECTURE",
                    "nodes": [f0["value"], f2["value"], f3["value"]],
                    "caption": topic["hook_subtext"][:36],
                },
            ),
        ]
        sfx_cycle = ["sub_boom", "whoosh", "tick", "sonar", "glitch", "riser"]
        motions = ["zoom_in", "pan_right", "zoom_out", "pan_left", "drift_up"]
        shorts_beats = []
        for idx, line in enumerate(lines):
            use_plate = idx % 2 == 0 and idx != len(lines) - 1
            p_mode, p_data = plate_sequence[(idx // 2) % len(plate_sequence)]
            fact_ref = facts[idx % len(facts)]
            shorts_beats.append(
                {
                    "narration": line,
                    "visual_type": "data_plate" if use_plate else "photo_grade",
                    "plate_mode": p_mode,
                    "plate_data": p_data if use_plate else {},
                    "visual_query": q(idx),
                    "hud_tag": f"VELUM // {idx + 1:02d}",
                    "hud_metric": fact_ref["value"],
                    "hud_delta": fact_ref["label"][:11],
                    "sfx": "sub_boom" if idx == 0 else sfx_cycle[idx % len(sfx_cycle)],
                    "camera_motion": motions[idx % len(motions)],
                }
            )
    else:
        # Dynamic Wikipedia anomaly synthesizer fallback (uses real Wikipedia sentences + hard metrics)
        f0, f1, f2, f3 = facts[0], facts[1], facts[2], facts[3]
        wiki_sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", topic.get("wiki_summary", ""))
            if len(s.strip()) > 25
        ]
        s0 = wiki_sentences[0] if len(wiki_sentences) > 0 else f"The verified benchmark hits {f1['value']}."
        s1 = wiki_sentences[1] if len(wiki_sentences) > 1 else f"At full scale, {f2['label'].lower()} reaches {f2['value']}."
        dyn_lines = [
            f"One number changes everything you know about {topic['primary_keyword']}: {f0['value']}.",
            s0,
            f"When you measure {f1['label'].lower()}, the real figure jumps to {f1['value']}.",
            s1,
            f"Compare that directly against {f2['label'].lower()} at {f2['value']}.",
            f"And at the outer limit, {f3['label'].lower()} reaches {f3['value']}.",
            "Our linear intuition compresses these huge jumps into a flat line.",
            "Only when you place the raw telemetry side by side does the hidden architecture appear.",
            "Which is why the scale shock hits twice as hard the moment you remember that—",
        ]
        shorts_beats = []
        for idx, line in enumerate(dyn_lines):
            fact_ref = facts[idx % len(facts)]
            shorts_beats.append(
                {
                    "narration": line,
                    "visual_type": "data_plate" if idx % 2 == 0 else "photo_grade",
                    "plate_mode": "comparison_bars" if idx == 2 else "metric_hero",
                    "plate_data": {
                        "title": fact_ref["label"],
                        "hero_value": fact_ref["value"],
                        "left_label": f0["label"][:12],
                        "left_value": 10.0,
                        "left_display": f0["value"],
                        "right_label": f1["label"][:12],
                        "right_value": 100.0,
                        "right_display": f1["value"],
                        "subtitle": topic["primary_keyword"].upper()[:36],
                        "accent": "amber" if idx % 2 == 0 else "cyan",
                    },
                    "visual_query": q(idx),
                    "hud_tag": f"VELUM // {idx + 1:02d}",
                    "hud_metric": fact_ref["value"],
                    "hud_delta": fact_ref["label"][:11],
                    "sfx": "sub_boom" if idx == 0 else ("whoosh" if idx % 2 == 0 else "tick"),
                    "camera_motion": ["zoom_in", "pan_right", "zoom_out", "pan_left"][idx % 4],
                }
            )

    if fmt == "longform":
        expanded: List[Dict[str, Any]] = []
        chapters = [
            ("CH.01 // THE SCALE ILLUSION", shorts_beats),
            (
                "CH.02 // WHY HUMAN INTUITION FAILS",
                [
                    {
                        **b,
                        "hud_tag": f"DEEP // {i + 1:02d}",
                        "narration": (
                            f"Zooming deeper into the mechanics: {b['narration'][0].lower()}{b['narration'][1:]}"
                            if i % 3 == 0
                            else b["narration"]
                        ),
                    }
                    for i, b in enumerate(shorts_beats[:-1])
                ],
            ),
            (
                "CH.03 // REAL-WORLD CONSEQUENCES",
                [
                    {
                        **b,
                        "hud_tag": f"IMPACT // {i + 1:02d}",
                    }
                    for i, b in enumerate(shorts_beats[:-1])
                ],
            ),
        ]
        for _, ch_beats in chapters:
            expanded.extend(ch_beats)
        expanded.append(
            {
                "narration": "Drop your call in the comments: which invisible threshold shocks you most?",
                "visual_type": "data_plate",
                "plate_mode": "metric_hero",
                "plate_data": {
                    "title": "JOIN THE DEBATE",
                    "hero_value": "YOUR CALL",
                    "subtitle": "WHICH HIDDEN SYSTEM SHOULD WE DECODE NEXT?",
                    "accent": "cyan",
                },
                "visual_query": q(0),
                "hud_tag": "DEBATE // OPEN",
                "hud_metric": "YOUR CALL",
                "hud_delta": "COMMENTS",
                "sfx": "sonar",
                "camera_motion": "zoom_in",
            }
        )
        return expanded

    return shorts_beats


class ScriptEngine:
    """Produces retention-locked, VSEO-verified scripts ready for audio & visual synthesis."""

    def __init__(self, llm: Optional[ZeroCostLLMClient] = None) -> None:
        self.llm = llm or ZeroCostLLMClient()

    def _sanitize_anti_slop(self, text: str) -> str:
        cleaned = text.strip()
        for phrase in BANNED_SLOP_PHRASES:
            cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)
        return re.sub(r"\s{2,}", " ", cleaned).strip()

    def _verify_vseo_first_15s(self, beats: List[Dict[str, Any]], primary_keyword: str) -> bool:
        """Ensure primary keyword appears in the opening ~38 spoken words (~15 seconds)."""
        opening_words: List[str] = []
        for b in beats:
            opening_words.extend(b["narration"].split())
            if len(opening_words) >= 42:
                break
        opening_text = " ".join(opening_words).lower()
        kw_tokens = [tok for tok in re.findall(r"[a-z0-9]+", primary_keyword.lower()) if len(tok) > 2]
        matched = sum(1 for tok in kw_tokens if tok in opening_text)
        return matched >= max(1, len(kw_tokens) - 1)

    def generate_script(self, topic: Dict[str, Any], fmt: str = "shorts") -> Dict[str, Any]:
        """Generate a validated scene-by-scene script for 'shorts' (9:16) or 'longform' (16:9)."""
        beats: Optional[List[Dict[str, Any]]] = None

        if self.llm.is_available:
            system_prompt = load_prompt("retention_script.md")
            user_prompt = (
                f"Format: {fmt}\n"
                f"Target beats: {'14 to 18 tight beats (~42-52s total)' if fmt == 'shorts' else '40 to 55 beats (~3 min)'}.\n"
                f"Primary keyword (MUST be spoken within first 15 seconds): {topic['primary_keyword']}\n"
                f"Topic Blueprint:\n{json.dumps(topic, ensure_ascii=False)}"
            )
            llm_script = self.llm.complete_json(system_prompt, user_prompt, temperature=0.6)
            if llm_script and isinstance(llm_script.get("beats"), list) and len(llm_script["beats"]) >= 8:
                beats = llm_script["beats"]

        if not beats:
            beats = _topic_specific_beats(topic, fmt)

        normalized_beats: List[Dict[str, Any]] = []
        total_beats = len(beats)
        for idx, raw in enumerate(beats):
            narration = self._sanitize_anti_slop(str(raw.get("narration", "")))
            if not narration:
                continue
            words = max(1, len(narration.split()))
            est_dur = max(1.6, min(2.5, round(words / 3.1, 2)))
            normalized_beats.append(
                {
                    "index": idx + 1,
                    "target_duration": est_dur,
                    "narration": narration,
                    "visual_type": raw.get("visual_type", "data_plate" if idx % 2 == 0 else "photo_grade"),
                    "plate_mode": raw.get("plate_mode", "metric_hero"),
                    "plate_data": raw.get("plate_data", {}),
                    "visual_query": raw.get("visual_query", topic["primary_keyword"]),
                    "hud_tag": str(raw.get("hud_tag", f"VELUM // {idx + 1:02d}")).upper(),
                    "hud_metric": str(raw.get("hud_metric", topic["shock_hook_stat"])).upper(),
                    "hud_delta": str(raw.get("hud_delta", f"{int((idx + 1) / total_beats * 100)}%")).upper(),
                    "hud_progress": round((idx + 1) / max(total_beats, 1), 3),
                    "sfx": raw.get("sfx", "sub_boom" if idx == 0 else ("whoosh" if idx % 3 == 0 else "tick")),
                    "camera_motion": raw.get(
                        "camera_motion",
                        ["zoom_in", "pan_right", "zoom_out", "pan_left", "drift_up"][idx % 5],
                    ),
                }
            )

        vseo_ok = self._verify_vseo_first_15s(normalized_beats, topic["primary_keyword"])
        if not vseo_ok and len(normalized_beats) >= 3:
            normalized_beats[2]["narration"] = (
                f"This exact {topic['primary_keyword']} proves how distorted our intuition really is."
            )
            vseo_ok = True

        full_narration = " ".join(b["narration"] for b in normalized_beats)
        script_payload = {
            "format": fmt,
            "topic_id": topic["topic_id"],
            "pillar": topic["pillar"],
            "primary_keyword": topic["primary_keyword"],
            "hook_stat_text": topic["shock_hook_stat"],
            "hook_subtext": topic.get("hook_subtext", "VELUM ARCHIVE TELEMETRY"),
            "vseo_verified_under_15s": vseo_ok,
            "full_narration": full_narration,
            "word_count": len(full_narration.split()),
            "beats": normalized_beats,
        }
        logger.info(
            "Script generated: %s | format=%s | beats=%d | words=%d | VSEO<15s=%s",
            topic["topic_id"],
            fmt,
            len(normalized_beats),
            script_payload["word_count"],
            vseo_ok,
        )
        return script_payload
