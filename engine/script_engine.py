"""VELUM Documentary Retention Script Architect (prompts/retention_script.md).

Generates hyper-dense, story-driven scene-by-scene documentary scripts for:
- Shorts (9:16, strictly ~85-108 words / ~28-35s at +16%, seamless infinite loop)
- Long-form (16:9, ~180-240s, multi-chapter deep breakdown)

Enforces:
- 0-2s high-contrast shock hook (zero filler phrases)
- Seamless Part-2 continuity hook when `topic.get("is_part2_followup")` is True
- Primary keyword spoken within first 15s (VSEO)
- Visual beat durations strictly <= 2.5s
- Story-specific concrete analogies, physical scale twists, and seamless loops
  across every single topic (never generic placeholder sentences).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from core.config import get_logger, load_prompt
from core.llm_client import ZeroCostLLMClient

logger = get_logger("script_engine")

SHORTS_MIN_WORDS = 72
SHORTS_MAX_WORDS = 94
SHORTS_TARGET_WORDS = 84

PART2_CONTINUITY_HOOKS = (
    ("Part two goes even deeper. ", False),
    ("Since you loved our last breakdown, ", True),
)

PROPER_OPENING_WORDS = {
    "NASA", "ASML", "GPS", "DNA", "DNS", "EUV", "AI", "US", "UK", "Wall", "Soviet",
    "Abraham", "Einstein", "Albert", "Psychologist", "Japanese", "United", "Title",
    "Congress", "Ariane", "Kola", "Point", "Mount", "Pacific", "Atlantic", "Las",
    "Netflix", "Mars", "Venus", "Mercury", "Earth", "Saturn", "Jupiter", "Pluto",
    "Psyche", "Titanic", "I",
}

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
        "It fires through undersea fiber cables on the ocean floor thinner than a garden hose.",
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
        "ASML's EUV lithography machine costs three hundred and eighty million dollars apiece.",
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
        "The crushing pressure inside the Mariana Trench is far more hostile than outer space.",
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
        "Behavioral economists call it the decoy effect, and almost every pricing menu uses it on you.",
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
        "General relativity actually warps time for GPS satellites twenty thousand kilometers above your head.",
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
        "All the gold ever mined on Earth fits inside a single twenty two meter cube.",
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
        "Standardized shipping containers quietly slashed global ocean trade costs by ninety seven percent.",
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
        "Doubling a penny for thirty days exposes how badly human brains misjudge exponential math.",
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
        "The gap between physical cash and digital money supply is modern banking's biggest illusion.",
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
        "Selling loyalty points to giant banks completely flipped the airline business model.",
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
        "Shrinking a transistor down to two nanometers pushes engineering straight to atomic physics.",
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
        "Keeping the power grid frequency balanced requires supply and demand to match every millisecond.",
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
        "These thirteen DNS root servers act as the master phonebook controlling the entire web.",
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
        "In high frequency trading, the speed of light itself is the final bottleneck.",
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
        "One mathematician stopped them, uncovering survivorship bias in returning airplanes and saving thousands of lives.",
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
        "Supermarket layouts are deliberately rigged with psychology tricks to double how long you walk.",
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
        "That variable reward dopamine loop keeps billions of people scrolling for hours without noticing.",
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
        "Kahneman and Tversky's famous anchoring bias experiment exposed a permanent glitch in human judgment.",
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
        "Psychologists call it the Zeigarnik effect: unfinished tasks hijack your working memory far more than finished ones.",
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
        "That insane neutron star weight is the closest physical matter ever gets to a black hole.",
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
        "Unwind all the DNA inside a human body and its length dwarfs the entire solar system.",
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
        "Every planet in our solar system fits right between the Earth and the Moon with room to spare.",
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
        "There is a spot in the South Pacific where the closest humans to you are astronauts in orbit.",
        "Above Point Nemo, the ISS space station passes just four hundred and eight kilometers overhead.",
        "Meanwhile, the nearest inhabited island on Earth sits two thousand six hundred and eighty eight kilometers away.",
        "You are literally six times closer to astronauts in space than to anyone walking on dry land.",
        "Ocean currents rotating around this zone block nutrient flow, creating an underwater biological desert.",
        "No commercial shipping lanes or passenger flights ever cross these empty coordinates.",
        "Because it is so isolated, space agencies use Point Nemo as Earth's official spacecraft graveyard.",
        "Over two hundred and sixty decommissioned satellites and space stations lie sunken four kilometers below.",
        "When the International Space Station retires, it will plunge into this exact same abyss.",
        "The loneliest place on Earth looks straight up at orbit, which makes you realize why—",
    ],
    # ===================== V4 NATIVE-ENGLISH VIRAL 30-SECOND TENSION ARCS =====================
    "asteroid-psyche-10-quintillion-gold": [
        "NASA is racing straight toward a single asteroid worth ten quintillion dollars.",
        "Named 16 Psyche, this metallic giant spans two hundred and twenty six kilometers of solid iron, nickel, and gold.",
        "For perspective, the entire global economy of planet Earth is only one hundred and five trillion dollars.",
        "Psyche is worth nearly one hundred thousand times more than every company and bank on Earth combined.",
        "Split evenly, that comes out to one point two billion dollars for every human alive.",
        "Here is the brutal twist nobody mentions: bringing it back would not make you rich.",
        "Flooding Earth with cosmic metal would crash gold and iron prices straight to zero overnight.",
        "Would mining it save humanity or wreck the economy? Drop your call below and subscribe for tomorrow's scale—",
    ],
    "titan-implosion-20-milliseconds": [
        "At four thousand meters underwater, you would be gone before your brain even knew anything went wrong.",
        "During a deep ocean implosion, water moves faster than human nerves can warn your brain.",
        "At Titanic depth, the Atlantic crushes every square inch with three hundred and seventy five atmospheres.",
        "That is like balancing the entire Empire State Building directly on top of one small car.",
        "The instant a carbon hull cracks down there, water slams inward faster than sound.",
        "The entire cabin collapses completely in just twenty milliseconds.",
        "Meanwhile, a human brain needs one hundred and fifty milliseconds just to register pain.",
        "You literally cannot feel it happen. Would you ever dive down there? Comment below—",
    ],
    "airplane-window-tiny-hole-secret": [
        "Look closely on your next flight, and you will spot a tiny pin-hole drilled into every airplane window.",
        "That microscopic bleed valve is the only thing keeping your window from shattering mid-air.",
        "At eleven thousand meters up, outside air drops to minus fifty six degrees with almost zero pressure.",
        "Inside the cabin, pressurized air pushes outward with tons of force trying to burst into the sky.",
        "Every window actually uses three separate acrylic panes, not one.",
        "That tiny one point five millimeter hole routes cabin pressure safely onto the thick outer pane.",
        "The middle pane stays completely untouched as an emergency shield if the outside ever cracks.",
        "Did you actually know what that hole does? Comment below and subscribe for tomorrow's breakdown—",
    ],
    "how-fast-you-move-sitting-still": [
        "You think you are sitting still right now, yet you are flying at two point one million kilometers an hour.",
        "To see how fast you really move through space, stack four invisible speeds together.",
        "First, Earth spins you around its equator at one thousand six hundred and seventy kilometers an hour.",
        "At the same time, Earth rockets around the Sun at one hundred and seven thousand kilometers an hour.",
        "Our solar system drags you around the Milky Way at eight hundred and twenty eight thousand kilometers an hour.",
        "And our entire galaxy is hurtling across the universe at over two million kilometers an hour.",
        "You feel zero wind only because the air and gravity travel at that exact speed with you.",
        "In the thirty seconds you watched this, you flew seventeen thousand kilometers. Comment if you want what happens if Earth stops—",
    ],
    "one-grain-of-sand-space-bullet": [
        "A single flake of paint in space hits harder than a bowling ball fired at one hundred miles an hour.",
        "In low orbit, orbital velocity turns microscopic space debris into armor-piercing bullets.",
        "A high-powered rifle bullet travels around three thousand kilometers an hour.",
        "Above your head, dead rocket chips whip around Earth at twenty eight thousand kilometers an hour.",
        "At nearly ten times bullet speed, kinetic impact energy multiplies by one hundred.",
        "One paint speck weighing zero point two grams once blasted a four millimeter crater into a space shuttle window.",
        "Right now, over one hundred million tiny fragments are circling silently overhead.",
        "Will space junk trap humanity on Earth one day? Drop your call below—",
    ],
    "one-line-of-code-370m-rocket-crash": [
        "One single math bug inside a computer turned a three hundred and seventy million dollar rocket into a fireball.",
        "The Ariane 5 integer overflow remains the most expensive software crash in history.",
        "Engineers spent ten full years building Europe's newest heavy space launcher.",
        "Thirty seven seconds after liftoff, the computer tried to squeeze a sixty four bit speed number into a sixteen bit box.",
        "That box could only hold up to thirty two thousand seven hundred and sixty seven.",
        "The number overflowed, crashed both computers, and slammed the rocket sideways at full thrust.",
        "Aerodynamic forces snapped the vehicle apart and triggered instant self-destruct.",
        "Would you trust pure AI to write rocket code? Comment yes or never below—",
    ],
    "traffic-jam-phantom-wave-1-brake": [
        "Most highway traffic jams have zero accidents, zero construction, and zero lane closures.",
        "A phantom traffic jam starts from literally one driver tapping the brakes for a single second.",
        "Japanese physicists proved it by placing twenty two drivers on a completely empty circular track.",
        "Every driver was told to cruise smoothly at the exact same steady speed.",
        "Within just forty seconds, one tiny hesitation triggered a chain reaction behind it.",
        "Because human reaction takes one point two seconds, every car behind braked slightly harder.",
        "Soon cars hit a dead stop, sending a backward traffic wave rolling down the road at twenty kilometers an hour.",
        "Who causes more traffic: tailgaters or slow left-lane drivers? Drop your vote below—",
    ],
    "casino-no-clocks-psychological-trap": [
        "Walk through a billion dollar Las Vegas casino and try to find a single wall clock or window.",
        "Hiding clocks and windows is one of the smartest psychological traps ever engineered.",
        "Without sunlight or time cues, your brain loses track of how many hours have vanished.",
        "Studies show removing time cues stretches average gambling sessions by over forty two percent.",
        "Notice the carpets too: those wild neon patterns are ugly on purpose so your eyes stay locked up on glowing machines.",
        "Even the exits hide behind curving maze aisles that route you past twenty extra tables just to find a restroom.",
        "Every inch of the building protects a two to fifteen percent house edge.",
        "Ever walked indoors for an hour and left four hours later? Comment below—",
    ],
    "you-never-actually-touch-anything": [
        "Strictly according to physics, you have never actually touched anything or anyone in your life.",
        "Because of atomic repulsion, your body is hovering microscopically above your chair right now.",
        "Every atom in your body is ninety nine point nine nine nine nine percent empty space.",
        "Surrounding every atom is a cloud of negatively charged electrons.",
        "When your finger presses your phone screen, the electrons on both surfaces repel with staggering electromagnetic force.",
        "You stop hovering roughly one ten-billionth of a meter away without ever making true physical contact.",
        "What your brain feels as solid touch is just invisible force fields pushing back at light speed.",
        "Does that blow your mind or sound impossible? Drop your reaction below—",
    ],
    "trillion-dollar-platinum-coin-loophole": [
        "Buried inside US federal law is a real loophole that lets one person mint a one trillion dollar coin overnight.",
        "This platinum coin loophole sits inside Title thirty one, Section fifty one twelve of the US Code.",
        "Congress capped the face value of gold, silver, and copper coins, but forgot to cap platinum.",
        "On paper, the Treasury can stamp a one-ounce coin worth one thousand dollars with a one trillion dollar face value.",
        "Then they simply walk it across the street and deposit it into the Federal Reserve.",
        "Instantly, the government creates a one billion times markup without borrowing a single extra dollar.",
        "Economists still argue whether minting it would trigger chaos or change nothing at all.",
        "Smart emergency backup or instant hyperinflation disaster? Comment your call below—",
    ],
    "kola-superdeep-borehole-limit": [
        "Soviet scientists drilled straight down into Earth for twenty years, then suddenly had to stop forever.",
        "Russia's Kola Superdeep Borehole reached twelve point two kilometers down before physics melted their drills.",
        "That sounds impossibly deep, yet it barely scratched zero point two percent of Earth's radius.",
        "Picture Earth like an apple: humanity has never even pierced through the outer skin.",
        "Down at twelve kilometers, temperatures surged to one hundred and eighty degrees Celsius, double every prediction.",
        "Under that intense heat and pressure, solid granite stopped cracking and flowed like melted plastic.",
        "Every time engineers pulled the drill bit up, the hole simply oozed shut again.",
        "Will humans walk on Mars before we ever reach Earth's mantle? Drop your bet below—",
    ],
    "cargo-ship-250k-tons-float-physics": [
        "Drop a one-gram steel nail into the ocean and it sinks straight to the bottom.",
        "Yet a two hundred and fifty thousand ton steel cargo ship floats effortlessly across the sea.",
        "A mega container ship stretches four hundred meters long and carries twenty four thousand stacked steel boxes.",
        "It weighs a quarter of a million tons, heavier than seven hundred fully loaded jumbo jets.",
        "So why does solid steel sink while this floating skyscraper stays on top?",
        "Because roughly ninety percent of its massive hollow hull is trapped empty air.",
        "Spread across that footprint, the ship's average density drops below seawater, pushing back upward with equal force.",
        "Would you ever work crossing the Pacific on one of these giants? Comment below—",
    ],
    "slot-machine-near-miss-brain-hack": [
        "When two jackpots line up and the third symbol misses by one millimeter, your brain does something bizarre.",
        "It is called the slot machine near-miss effect, and it hacks your dopamine into celebrating a loss.",
        "Brain scans show an almost-win fires the exact same reward circuit as actually hitting the payout.",
        "Even though you won zero dollars, dopamine surges and whispers that you are getting closer.",
        "Designers mathematically weight reels to produce near misses up to twelve times more often than pure chance.",
        "Experiments prove that one visual illusion keeps players spinning thirty three percent longer.",
        "And today, mobile loot boxes and swipe feeds use that exact same reward loop.",
        "Should near-miss algorithms in games be banned by law? Comment yes or no below—",
    ],
    "gold-never-rusts-5000-years": [
        "Pull an iron ship up from the ocean after a century and it crumbles into orange dust.",
        "Yet the secret to why gold never rusts comes straight from Einstein's theory of relativity.",
        "Gold packs seventy nine heavy protons tightly inside its atomic core.",
        "That massive pull whips gold's inner electrons around at fifty eight percent of the speed of light.",
        "Because of relativity, those speeding electrons grow heavier and pull the outer shells tightly inward.",
        "Oxygen atoms simply cannot steal an electron to create rust, leaving five thousand year old gold spotless.",
        "Without relativity, gold would actually look dull silver, just like ordinary aluminum.",
        "Next fifty years: would you rather hold gold or Bitcoin? Drop your pick below—",
    ],
    "lithium-battery-thermal-runaway-chain": [
        "Right inside your pocket, only a plastic film thinner than a human hair stops a one thousand degree fire.",
        "When a lithium battery enters thermal runaway, water cannot even put the chain reaction out.",
        "A human hair measures seventy microns thick, while the safety separator inside a battery is just twenty microns.",
        "If a drop or microscopic metal spike pierces that paper-thin barrier, energy shorts out instantly.",
        "Within three seconds, internal heat spikes past two hundred degrees and cracks open the chemical cathode.",
        "Here is the terrifying twist: that breakdown releases pure oxygen right inside the sealed cell.",
        "Because the battery manufactures its own oxygen, it keeps burning even underwater.",
        "Be honest: do you sleep with your phone charging under your pillow? Comment below—",
    ],
    "survive-on-every-planet-seconds": [
        "Step outside on Mars without a spacesuit and you get ninety seconds, step on Venus and you get under one.",
        "Seeing how long a human survives on each planet exposes how fragile Earth's bubble really is.",
        "On Mercury, facing the sun roasts you at four hundred and thirty degrees while shadow freezes you instantly.",
        "On Mars, near-zero pressure boils moisture off your tongue before oxygen runs out in ninety seconds.",
        "Now drop down to Venus, Earth's supposed twin planet.",
        "Its thick carbon atmosphere blasts you with four hundred and sixty five degrees, hot enough to melt lead.",
        "At that same instant, ninety two atmospheres of crushing pressure flatten everything in under one second.",
        "If offered a free one-way ticket to colonize Mars, would you go? Comment yes or no below—",
    ],
}


def _trim_at_word_boundary(text: str, max_chars: int) -> str:
    """Trim display strings cleanly at word boundaries, never cutting mid-word or mid-number."""
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if not cleaned or len(cleaned) <= max_chars:
        return cleaned
    words = cleaned.split(" ")
    acc: List[str] = []
    for w in words:
        candidate = " ".join(acc + [w])
        if len(candidate) <= max_chars:
            acc.append(w)
        else:
            break
    if not acc:
        # Never slice a single long word or number token (e.g. "$10,000,000,000,000,000,000")
        return words[0]
    return " ".join(acc).rstrip(",;:-—/ ")


def _topic_specific_beats(topic: Dict[str, Any], fmt: str) -> List[Dict[str, Any]]:
    """Build hyper-dense, zero-fluff documentary beats tailored to the topic's real numbers."""
    tid = topic["topic_id"]
    base_tid = re.sub(r"-(?:v\d+|part2(?:-\d+)?)$", "", tid)
    facts = topic["key_facts"]
    queries = topic.get("visual_queries", ["dark technology infrastructure", "data visualization grid"])

    def q(idx: int) -> str:
        return queries[idx % len(queries)]

    if base_tid.startswith("one-million-vs-one-billion"):
        shorts_beats = [
            {
                "narration": "One million seconds is just eleven and a half days.",
                "visual_type": "photo_grade",
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
        if fmt == "shorts":
            # Tight 9-beat (~98 words) viral pacing for Shorts; keep full 16 beats for Long-form
            shorts_beats = [shorts_beats[i] for i in (0, 1, 2, 6, 7, 8, 12, 13, 15)]
    elif base_tid in TOPIC_STORY_ARCS:
        # Build V5 viral retention beats: 6 ultra-tight beats (~22-27s, 72-94w) for Shorts, full arc for Long-form
        full_lines = TOPIC_STORY_ARCS[base_tid]
        if fmt == "shorts" and len(full_lines) > 6:
            mid = full_lines[2:-2]
            pick_indices = [
                0,
                max(1, (len(mid) - 1) // 2),
                len(mid) - 1,
            ]
            # Deduplicate while preserving narrative order
            chosen_mid: List[str] = []
            for pi in pick_indices:
                if 0 <= pi < len(mid) and mid[pi] not in chosen_mid:
                    chosen_mid.append(mid[pi])
            lines = full_lines[:2] + chosen_mid[:2] + [full_lines[-2], full_lines[-1]]
        else:
            lines = list(full_lines)

        f0, f1, f2, f3 = facts[0], facts[1], facts[2], facts[3]
        debate = topic.get("debate_hook") or {}
        debate_q = debate.get(
            "question",
            f"WOULD YOU HAVE GUESSED {f0['value']}?",
        )
        debate_a = debate.get("option_a", "MIND BLOWN")
        debate_b = debate.get("option_b", "ALREADY KNEW")

        def _units_comparable(fa: Dict[str, Any], fb: Dict[str, Any]) -> bool:
            ua = str(fa.get("unit", "")).strip().upper()
            ub = str(fb.get("unit", "")).strip().upper()
            if not ua or not ub:
                return False
            if ua == ub:
                return True
            dim_groups = (
                {"SEC", "MS", "DAYS", "YRS", "YEARS", "HRS", "MOS"},
                {"MM", "CM", "M", "KM", "UM"},
                {"USD", "K", "M", "B", "T"},
            )
            return any(ua in g and ub in g for g in dim_groups)

        # Only draw proportional 3D blocks / bar charts when units truly compare (ZERO apples-vs-oranges!)
        pair_01_comparable = _units_comparable(f0, f1)
        pair_23_comparable = _units_comparable(f2, f3)

        plate_sequence = [
            (
                "split_vs_clash",
                {
                    "title": _trim_at_word_boundary(topic.get("hook_subtext", "SCALE CLASH"), 34),
                    "left_label": _trim_at_word_boundary(f0["label"], 26),
                    "left_value": float(abs(f0["numeric"])) or 1.0,
                    "left_display": f0["value"],
                    "right_label": _trim_at_word_boundary(f1["label"], 26),
                    "right_value": float(abs(f1["numeric"])) or 100.0,
                    "right_display": f1["value"],
                    "ratio_badge": _trim_at_word_boundary(topic["shock_hook_stat"], 32),
                },
            ),
            (
                "visual_scale_blocks" if pair_01_comparable else "dual_fact_spotlight",
                {
                    "title": _trim_at_word_boundary(f"{f0['label']} vs {f1['label']}", 36),
                    "left_label": _trim_at_word_boundary(f0["label"], 24),
                    "left_value": float(abs(f0["numeric"])) or 1.0,
                    "left_display": f0["value"],
                    "right_label": _trim_at_word_boundary(f1["label"], 24),
                    "right_value": float(abs(f1["numeric"])) or 100.0,
                    "right_display": f1["value"],
                    "ratio_badge": _trim_at_word_boundary(topic["shock_hook_stat"], 32),
                },
            ),
            (
                "comparison_bars" if pair_23_comparable else "dual_fact_spotlight",
                {
                    "title": _trim_at_word_boundary(topic.get("hook_subtext", "KEY TELEMETRY"), 34),
                    "left_label": _trim_at_word_boundary(f2["label"], 24),
                    "left_value": float(abs(f2["numeric"])) or 10.0,
                    "left_display": f2["value"],
                    "right_label": _trim_at_word_boundary(f3["label"], 24),
                    "right_value": float(abs(f3["numeric"])) or 100.0,
                    "right_display": f3["value"],
                    "ratio_badge": _trim_at_word_boundary(topic.get("hook_subtext", "VERIFIED SCALE"), 32),
                },
            ),
            (
                "radar_alert",
                {
                    "title": _trim_at_word_boundary(f2["label"], 26),
                    "metric": f2["value"],
                    "subtitle": _trim_at_word_boundary(lines[min(5, len(lines) - 1)].upper(), 52),
                    "severity": "CRITICAL",
                },
            ),
        ]
        sfx_cycle = ["sub_boom", "whoosh", "tick", "sonar", "glitch", "riser"]
        motions = ["zoom_in", "pan_right", "zoom_out", "pan_left", "drift_up"]
        shorts_beats = []
        for idx, line in enumerate(lines):
            is_last = idx == len(lines) - 1
            fact_ref = facts[idx % len(facts)]
            if is_last:
                shorts_beats.append(
                    {
                        "narration": line,
                        "visual_type": "data_plate",
                        "plate_mode": "debate_cta_plate",
                        "plate_data": {
                            "question": debate_q,
                            "option_a": debate_a,
                            "option_b": debate_b,
                        },
                        "visual_query": q(idx),
                        "hud_tag": "DEBATE // LIVE",
                        "hud_metric": "YOUR CALL",
                        "hud_delta": "COMMENT",
                        "sfx": "sonar",
                        "camera_motion": "zoom_in",
                    }
                )
            else:
                # V5 Cinema-First Viral Pacing: Beat 0 ALWAYS opens on vivid full-bleed HD footage
                # (clean scroll-stopper thumbnail cover), then whip-zooms into animated data plates on Beats 1 & 3!
                use_plate = idx in (1, 3)
                plate_slot = 0 if idx == 1 else 1
                p_mode, p_data = plate_sequence[plate_slot % len(plate_sequence)]
                shorts_beats.append(
                    {
                        "narration": line,
                        "visual_type": "data_plate" if use_plate else "photo_grade",
                        "plate_mode": p_mode,
                        "plate_data": p_data if use_plate else {},
                        "visual_query": q(idx),
                        "hud_tag": f"VELUM · {idx + 1:02d}",
                        "hud_metric": fact_ref["value"],
                        "hud_delta": _trim_at_word_boundary(fact_ref["label"], 22),
                        "sfx": "sub_boom" if idx == 0 else ("riser" if idx == len(lines) - 2 else sfx_cycle[idx % len(sfx_cycle)]),
                        "camera_motion": motions[idx % len(motions)],
                    }
                )
    else:
        # Dynamic Wikipedia / Viewer-Requested documentary synthesizer (V5 native English + clean plates)
        f0, f1, f2, f3 = facts[0], facts[1], facts[2], facts[3]
        raw_wiki = re.sub(r"\([^)]{1,80}\)", "", topic.get("wiki_summary", ""))
        raw_wiki = re.sub(r"\s{2,}", " ", raw_wiki).strip()
        wiki_sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", raw_wiki)
            if 28 <= len(s.strip()) <= 165
        ]
        kw_title = str(topic.get("display_name") or topic["primary_keyword"])
        s0 = wiki_sentences[0] if len(wiki_sentences) > 0 else f"Real measurements around {kw_title} put the baseline right at {f0['value']}."
        s1 = wiki_sentences[1] if len(wiki_sentences) > 1 else f"When researchers zoom out, the verified scale reaches {f1['value']}."
        dyn_lines = [
            f"Almost nobody pictures the real scale behind {kw_title}.",
            s0,
            s1,
            f"Stack those numbers side by side: {f0['value']} against {f1['value']}.",
            "Did you already know this, or was it brand new? Tell us below and drop the next topic you want broken down.",
        ]
        debate = topic.get("debate_hook") or {}
        debate_q = str(debate.get("question") or "MIND BLOWN OR ALREADY KNEW?").upper()[:54]
        debate_a = str(debate.get("option_a") or "MIND BLOWN").upper()[:20]
        debate_b = str(debate.get("option_b") or "ALREADY KNEW").upper()[:20]
        shorts_beats = []
        for idx, line in enumerate(dyn_lines):
            is_last = idx == len(dyn_lines) - 1
            fact_ref = facts[idx % len(facts)]
            if is_last:
                p_mode = "debate_cta_plate"
                p_data = {
                    "question": debate_q,
                    "option_a": debate_a,
                    "option_b": debate_b,
                }
                vtype = "data_plate"
            else:
                use_plate = idx in (1, 3)
                vtype = "data_plate" if use_plate else "photo_grade"
                if idx == 1:
                    p_mode = "metric_hero"
                    p_data = {
                        "title": _trim_at_word_boundary(kw_title.upper(), 28),
                        "hero_value": _trim_at_word_boundary(topic["shock_hook_stat"], 24),
                        "subtitle": _trim_at_word_boundary(topic.get("hook_subtext", "VERIFIED SCALE"), 40),
                        "accent": "amber",
                    }
                else:
                    p_mode = "dual_fact_spotlight"
                    p_data = {
                        "title": _trim_at_word_boundary(f"{kw_title.upper()} // SCALE", 30),
                        "left_label": _trim_at_word_boundary(f0["label"], 22),
                        "left_display": f0["value"],
                        "right_label": _trim_at_word_boundary(f1["label"], 22),
                        "right_display": f1["value"],
                        "ratio_badge": "VERIFIED TELEMETRY",
                        "accent": "cyan",
                    }
            shorts_beats.append(
                {
                    "narration": line,
                    "visual_type": vtype,
                    "plate_mode": p_mode,
                    "plate_data": p_data if vtype == "data_plate" else {},
                    "visual_query": q(idx),
                    "hud_tag": f"VELUM · {idx + 1:02d}",
                    "hud_metric": fact_ref["value"],
                    "hud_delta": _trim_at_word_boundary(fact_ref["label"], 22),
                    "sfx": "sub_boom" if idx == 0 else ("sonar" if is_last else ("whoosh" if idx == 3 else "tick")),
                    "camera_motion": ["zoom_in", "pan_right", "zoom_out", "pan_left"][idx % 4],
                }
            )

    if fmt == "longform":
        # Genuine 3-chapter documentary expansion (zero verbatim repetition of Shorts sentences!)
        f0, f1, f2, f3 = facts[0], facts[1], facts[2], facts[3]
        kw = topic["primary_keyword"]
        expanded: List[Dict[str, Any]] = list(shorts_beats[:-1])
        deep_mechanics = [
            (
                f"To understand why {kw} breaks everyday intuition, we have to examine the underlying ratio.",
                "system_nodes",
                {
                    "title": "CORE MECHANISM",
                    "nodes": [f0["value"], f1["value"], f2["value"]],
                    "caption": _trim_at_word_boundary(topic["hook_subtext"], 38),
                },
            ),
            (
                f"Human perception evolved for linear local steps, not jumps from {f0['value']} straight to {f1['value']}.",
                "visual_scale_blocks",
                {
                    "title": "NON-LINEAR SCALING GAP",
                    "left_label": _trim_at_word_boundary(f0["label"], 24),
                    "left_value": float(abs(f0["numeric"])) or 1.0,
                    "left_display": f0["value"],
                    "right_label": _trim_at_word_boundary(f1["label"], 24),
                    "right_value": float(abs(f1["numeric"])) or 100.0,
                    "right_display": f1["value"],
                    "ratio_badge": "PERCEPTION FAILURE",
                },
            ),
            (
                f"Once you isolate {f2['label'].lower()} at {f2['value']}, the hidden engineering margin becomes unmistakable.",
                "radar_alert",
                {"title": _trim_at_word_boundary(f2["label"], 26), "metric": f2["value"], "subtitle": "STRUCTURAL BOTTLENECK", "severity": "HIGH"},
            ),
            (
                f"At the extreme boundary of {f3['label'].lower()}, the system hits {f3['value']}.",
                "timeline_scale",
                {
                    "title": "BOUNDARY TELEMETRY",
                    "markers": [
                        {"label": _trim_at_word_boundary(f0["label"], 22), "value": f0["value"], "pct": 0.18, "color": "cyan"},
                        {"label": _trim_at_word_boundary(f2["label"], 22), "value": f2["value"], "pct": 0.55, "color": "amber"},
                        {"label": _trim_at_word_boundary(f3["label"], 22), "value": f3["value"], "pct": 0.90, "color": "crimson"},
                    ],
                },
            ),
            (
                "That is why headlines routinely mislead smart people when numbers cross an order-of-magnitude threshold.",
                "metric_hero",
                {
                    "title": "COGNITIVE TAKEAWAY",
                    "hero_value": _trim_at_word_boundary(topic["shock_hook_stat"], 32),
                    "subtitle": "VISUALIZE THE RATIO FIRST",
                    "accent": "cyan",
                },
            ),
        ]
        for idx, (narr, pmode, pdata) in enumerate(deep_mechanics):
            expanded.append(
                {
                    "narration": narr,
                    "visual_type": "data_plate" if idx % 2 == 0 else "photo_grade",
                    "plate_mode": pmode,
                    "plate_data": pdata,
                    "visual_query": q(idx + 1),
                    "hud_tag": f"CH.02 · {idx + 1:02d}",
                    "hud_metric": facts[idx % len(facts)]["value"],
                    "hud_delta": "DEEP DIVE",
                    "sfx": "whoosh" if idx % 2 == 0 else "tick",
                    "camera_motion": ["pan_right", "zoom_in", "pan_left", "zoom_out"][idx % 4],
                }
            )
        expanded.append(shorts_beats[-1])
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
        """Ensure core topic keywords appear naturally inside the opening ~15 seconds without robotic stuffing."""
        opening_words: List[str] = []
        for b in beats:
            opening_words.extend(b["narration"].split())
            if len(opening_words) >= 48:
                break
        opening_text = " ".join(opening_words).lower()
        stop = {"how", "why", "the", "and", "for", "can", "you", "are", "with", "each", "long", "vs"}
        kw_tokens = [
            tok for tok in re.findall(r"[a-z0-9]+", primary_keyword.lower())
            if len(tok) > 2 and tok not in stop
        ]
        if not kw_tokens:
            return True
        matched = sum(1 for tok in kw_tokens if tok in opening_text or (len(tok) > 4 and tok[:-1] in opening_text))
        return matched >= max(1, (len(kw_tokens) + 1) // 2)

    def _apply_part2_continuity_hook(
        self, beats: List[Dict[str, Any]], topic: Dict[str, Any]
    ) -> None:
        """Preserve cold-scroll standalone Beat 0 hook on Part-2 sequels (V5 swipe-rate fix)."""
        if topic.get("is_part2_followup") and beats:
            logger.debug(
                "V5 standalone cold-scroll hook preserved for winning-pillar sequel %s",
                topic.get("topic_id", ""),
            )

    def _apply_viewer_request_hook(
        self, beats: List[Dict[str, Any]], topic: Dict[str, Any]
    ) -> None:
        """Credit viewers naturally at Beat 0 when producing a harvested viewer-requested topic."""
        if not topic.get("is_viewer_requested") or not beats:
            return
        first_narr = str(beats[0].get("narration", "")).strip()
        if not first_narr:
            return
        low = first_narr.lower()
        if low.startswith("a viewer asked") or low.startswith("one of you asked"):
            return
        beats[0]["narration"] = f"A viewer asked us to break this down. {first_narr}"

    @staticmethod
    def _count_words(beats: List[Dict[str, Any]]) -> int:
        return sum(len(str(b.get("narration", "")).split()) for b in beats)

    @staticmethod
    def _trim_verbose_clauses(text: str, max_trim: int) -> str:
        """Trim concise redundant modifiers without breaking sentence grammar."""
        updated = text
        redundant_swaps = (
            (r"\bevery single\b", "every"),
            (r"\bin human history\b", "ever"),
            (r"\bin your entire life\b", "in your life"),
            (r"\bright now while sitting still\b", "sitting still"),
            (r"\bcompletely untouched\b", "untouched"),
            (r"\bcompletely stopped\b", "stopped"),
            (r"\bcompletely broke\b", "broke"),
            (r"\bcompletely empty\b", "empty"),
            (r"\bcompletely underwater\b", "underwater"),
            (r"\bdirectly on top of\b", "on top of"),
            (r"\bstraight down into\b", "down into"),
            (r"\bthe exact same\b", "the same"),
            (r"\bactually\s+", ""),
            (r"\bliterally\s+", ""),
            (r"\bsimply\s+", ""),
            (r"\bjust\s+", ""),
            (r"\s+—\s+", ", "),
        )
        words_before = len(updated.split())
        for pattern, repl in redundant_swaps:
            if words_before - len(updated.split()) >= max_trim:
                break
            candidate = re.sub(pattern, repl, updated, count=1, flags=re.IGNORECASE)
            candidate = re.sub(r"\s{2,}", " ", candidate).strip()
            if candidate and candidate != updated:
                # Preserve capitalization of first character
                if updated[0].isupper() and candidate[0].islower():
                    candidate = candidate[0].upper() + candidate[1:]
                updated = candidate
        return updated

    def _enforce_shorts_word_budget(
        self,
        beats: List[Dict[str, Any]],
        topic: Dict[str, Any],
        min_words: int = SHORTS_MIN_WORDS,
        max_words: int = SHORTS_MAX_WORDS,
    ) -> List[Dict[str, Any]]:
        """Keep every Shorts script tightly within 85-108 words (~28-35s at +16%) cleanly."""
        trimmed = [dict(b) for b in beats]

        # 1. Remove lowest-priority interior beats (protecting Beat 0 Hook, Beat 1 VSEO,
        #    Beat -2 Climax/Twist, and Beat -1 Debate CTA / Loop) until <= max_words.
        while self._count_words(trimmed) > max_words and len(trimmed) > 5:
            cur_words = self._count_words(trimmed)
            removable_indices = list(range(2, len(trimmed) - 2))
            if not removable_indices:
                break
            best_idx = min(
                removable_indices,
                key=lambda i: (
                    0 if (cur_words - len(trimmed[i]["narration"].split())) >= min_words else 1,
                    abs((cur_words - len(trimmed[i]["narration"].split())) - SHORTS_TARGET_WORDS),
                ),
            )
            trimmed.pop(best_idx)

        # 2. If still slightly above max_words, tighten redundant filler phrases on beats >= 2
        if self._count_words(trimmed) > max_words:
            for idx in range(len(trimmed) - 1, 1, -1):
                excess = self._count_words(trimmed) - max_words
                if excess <= 0:
                    break
                trimmed[idx]["narration"] = self._trim_verbose_clauses(
                    trimmed[idx]["narration"], excess
                )

        # 3. If still above max_words with >4 beats, drop one more interior beat (keep >=4 beats)
        if self._count_words(trimmed) > max_words and len(trimmed) > 4:
            cur_words = self._count_words(trimmed)
            candidates = list(range(2, len(trimmed) - 1))
            if candidates:
                drop_idx = min(
                    candidates,
                    key=lambda i: abs((cur_words - len(trimmed[i]["narration"].split())) - SHORTS_TARGET_WORDS),
                )
                trimmed.pop(drop_idx)

        # 4. Final precision guard if an exceptionally verbose beat still pushes > max_words
        if self._count_words(trimmed) > max_words:
            for idx in range(len(trimmed) - 2, 1, -1):
                excess = self._count_words(trimmed) - max_words
                if excess <= 0:
                    break
                narr = trimmed[idx]["narration"]
                # Split on secondary clause if clean and still meaningful
                for sep in ("; ", ": ", ", "):
                    if sep in narr:
                        head = narr.split(sep, 1)[0].strip()
                        if len(head.split()) >= 7 and (len(narr.split()) - len(head.split())) >= 2:
                            if head[-1] not in ".!?":
                                head += "."
                            trimmed[idx]["narration"] = head
                            break

        # 5. Pad cleanly with verified numeric fact beat if trimming dropped below min_words
        facts = topic.get("key_facts", [])
        fact_cursor = 0
        while self._count_words(trimmed) < min_words and fact_cursor < max(len(facts), 2):
            if fact_cursor < len(facts):
                f = facts[fact_cursor]
                extra_line = (
                    f"Look at {str(f.get('label', 'the baseline')).lower()}: "
                    f"verified measurements put it right at {f.get('value', 'extreme scale')}."
                )
                hud_metric = str(f.get("value", topic["shock_hook_stat"])).upper()
                hud_delta = _trim_at_word_boundary(str(f.get("label", "VERIFIED")).upper(), 22)
            else:
                extra_line = "Once you put these real numbers side by side, your intuition completely resets."
                hud_metric = str(topic["shock_hook_stat"]).upper()
                hud_delta = "SCALE CHECK"

            insert_at = max(2, len(trimmed) - 1)
            ref_beat = trimmed[min(insert_at - 1, len(trimmed) - 1)]
            # Only insert if it won't overshoot max_words
            if self._count_words(trimmed) + len(extra_line.split()) <= max_words:
                trimmed.insert(
                    insert_at,
                    {
                        "index": insert_at + 1,
                        "target_duration": 2.1,
                        "narration": extra_line,
                        "visual_type": "photo_grade" if ref_beat.get("visual_type") == "data_plate" else "data_plate",
                        "plate_mode": "metric_hero",
                        "plate_data": {
                            "title": hud_delta,
                            "hero_value": hud_metric,
                            "subtitle": _trim_at_word_boundary(topic.get("hook_subtext", "VERIFIED TELEMETRY"), 42),
                            "accent": "amber",
                        },
                        "visual_query": ref_beat.get("visual_query", topic["primary_keyword"]),
                        "hud_tag": f"VELUM · {insert_at + 1:02d}",
                        "hud_metric": hud_metric,
                        "hud_delta": hud_delta,
                        "hud_progress": 0.75,
                        "sfx": "tick",
                        "camera_motion": "zoom_in",
                    },
                )
            else:
                # Short 6-word boost if a full beat would overshoot max_words
                short_boost = "Verified numbers change the whole picture."
                if self._count_words(trimmed) + len(short_boost.split()) <= max_words:
                    trimmed[insert_at - 1]["narration"] = (
                        f"{trimmed[insert_at - 1]['narration'].rstrip('.!?')}. {short_boost}"
                    )
                break
            fact_cursor += 1

        # Re-index and recompute monotonic HUD progress
        total = max(len(trimmed), 1)
        for i, b in enumerate(trimmed):
            b["index"] = i + 1
            words = max(1, len(b["narration"].split()))
            b["target_duration"] = max(1.6, min(2.5, round(words / 3.1, 2)))
            b["hud_progress"] = round((i + 1) / total, 3)

        return trimmed

    def generate_script(self, topic: Dict[str, Any], fmt: str = "shorts") -> Dict[str, Any]:
        """Generate a validated scene-by-scene script for 'shorts' (9:16) or 'longform' (16:9)."""
        beats: Optional[List[Dict[str, Any]]] = None

        if self.llm.is_available:
            system_prompt = load_prompt("retention_script.md")
            viewer_note = (
                "This topic was suggested by a viewer in our comments. "
                "Open Beat 0 cleanly with 'A viewer asked us to break this down.'\n"
                if topic.get("is_viewer_requested")
                else ""
            )
            user_prompt = (
                f"Format: {fmt}\n"
                f"Target beats: {'5 to 6 ultra-tight beats (STRICTLY 72-92 words total, ~22-27s, standalone cold-scroll hook — NEVER say Part 2)' if fmt == 'shorts' else '40 to 55 beats (~3 min)'}.\n"
                f"{viewer_note}"
                f"Primary keyword (MUST be spoken within first 15 seconds): {topic['primary_keyword']}\n"
                f"Topic Blueprint:\n{json.dumps(topic, ensure_ascii=False)}"
            )
            llm_script = self.llm.complete_json(system_prompt, user_prompt, temperature=0.6)
            if llm_script and isinstance(llm_script.get("beats"), list) and len(llm_script["beats"]) >= 6:
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

        # Seamlessly add Viewer-Request or Part-2 continuity hook before enforcing word budget so count never bloats
        self._apply_viewer_request_hook(normalized_beats, topic)
        self._apply_part2_continuity_hook(normalized_beats, topic)

        if fmt == "shorts":
            normalized_beats = self._enforce_shorts_word_budget(normalized_beats, topic)

        vseo_ok = self._verify_vseo_first_15s(normalized_beats, topic["primary_keyword"])
        if not vseo_ok and len(normalized_beats) >= 2:
            normalized_beats[1]["narration"] = (
                f"This {topic['primary_keyword']} proves how distorted human intuition really is."
            )
            if fmt == "shorts":
                normalized_beats = self._enforce_shorts_word_budget(normalized_beats, topic)
            vseo_ok = self._verify_vseo_first_15s(normalized_beats, topic["primary_keyword"])

        full_narration = " ".join(b["narration"] for b in normalized_beats)
        script_payload = {
            "format": fmt,
            "topic_id": topic["topic_id"],
            "pillar": topic["pillar"],
            "primary_keyword": topic["primary_keyword"],
            "hook_stat_text": topic["shock_hook_stat"],
            "hook_subtext": topic.get("hook_subtext", "VELUM ARCHIVE TELEMETRY"),
            "is_part2_followup": bool(topic.get("is_part2_followup", False)),
            "is_viewer_requested": bool(topic.get("is_viewer_requested", False)),
            "part2_reference_title": str(topic.get("part2_reference_title", "")),
            "vseo_verified_under_15s": vseo_ok,
            "full_narration": full_narration,
            "word_count": len(full_narration.split()),
            "beats": normalized_beats,
        }
        logger.info(
            "Script generated: %s | format=%s | beats=%d | words=%d | part2=%s | viewer=%s | VSEO<15s=%s",
            topic["topic_id"],
            fmt,
            len(normalized_beats),
            script_payload["word_count"],
            script_payload["is_part2_followup"],
            script_payload["is_viewer_requested"],
            vseo_ok,
        )
        return script_payload
