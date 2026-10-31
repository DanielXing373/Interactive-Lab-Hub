# Tarot keywords (upright only)

Three or four keywords per card, from the common Rider–Waite–Smith reading. `tarot.py` hands the drawn card's
keywords to Qwen so a 0.8B model stays on the right meaning: in our test it knew the famous cards
(The Tower, Three of Swords) but gave generic answers for less famous ones (Eight of Wands).

Format: one card per line, `- Card name: keyword, keyword, keyword`. Keep it that way, tarot.py parses it.

## Major Arcana

- The Fool: new beginnings, spontaneity, a leap of faith, innocence
- The Magician: willpower, skill, resourcefulness, manifestation
- The High Priestess: intuition, hidden knowledge, mystery, inner voice
- The Empress: abundance, nurturing, fertility, nature
- The Emperor: authority, structure, stability, leadership
- The Hierophant: tradition, guidance, institutions, shared beliefs
- The Lovers: love, harmony, partnership, an important choice
- The Chariot: determination, victory, control, moving forward
- Strength: courage, inner strength, patience, compassion
- The Hermit: solitude, reflection, inner guidance, searching
- Wheel of Fortune: change, cycles, luck, turning point
- Justice: fairness, truth, cause and effect, balance
- The Hanged Man: pause, surrender, a new perspective, waiting
- Death: endings, transformation, transition, letting go
- Temperance: balance, moderation, patience, healing
- The Devil: temptation, attachment, habits, restriction
- The Tower: sudden upheaval, collapse, revelation, awakening
- The Star: hope, renewal, inspiration, calm
- The Moon: illusion, uncertainty, dreams, the subconscious
- The Sun: joy, success, warmth, vitality
- Judgement: reflection, renewal, a calling, reckoning
- The World: completion, fulfillment, wholeness, travel

## Wands

- Ace of Wands: inspiration, new energy, a spark, potential
- Two of Wands: planning, future vision, decisions, first steps
- Three of Wands: expansion, foresight, progress, looking ahead
- Four of Wands: celebration, home, harmony, milestones
- Five of Wands: competition, conflict, rivalry, friction
- Six of Wands: victory, recognition, public success, confidence
- Seven of Wands: standing your ground, defense, perseverance, challenge
- Eight of Wands: speed, swift action, news arriving, momentum
- Nine of Wands: resilience, persistence, last stretch, guardedness
- Ten of Wands: burden, heavy responsibility, overload, hard work
- Page of Wands: curiosity, enthusiasm, exploration, good news
- Knight of Wands: adventure, action, passion, impulsiveness
- Queen of Wands: confidence, warmth, determination, charisma
- King of Wands: vision, leadership, boldness, entrepreneurship

## Cups

- Ace of Cups: new feelings, love, compassion, emotional opening
- Two of Cups: partnership, mutual attraction, connection, unity
- Three of Cups: friendship, celebration, community, joy
- Four of Cups: apathy, contemplation, missed offers, boredom
- Five of Cups: loss, regret, disappointment, grief
- Six of Cups: nostalgia, childhood memories, innocence, kindness
- Seven of Cups: choices, illusions, wishful thinking, daydreams
- Eight of Cups: walking away, moving on, searching for meaning, withdrawal
- Nine of Cups: contentment, wishes fulfilled, satisfaction, comfort
- Ten of Cups: family happiness, harmony, emotional fulfillment, home
- Page of Cups: creativity, intuition, a sweet message, curiosity
- Knight of Cups: romance, charm, following the heart, an offer
- Queen of Cups: empathy, emotional security, care, intuition
- King of Cups: emotional balance, calm, diplomacy, generosity

## Swords

- Ace of Swords: clarity, breakthrough, truth, a new idea
- Two of Swords: indecision, stalemate, a difficult choice, avoidance
- Three of Swords: heartbreak, sorrow, grief, painful truth
- Four of Swords: rest, recovery, contemplation, retreat
- Five of Swords: conflict, defeat, winning at a cost, tension
- Six of Swords: transition, moving on, calmer waters, travel
- Seven of Swords: strategy, stealth, deception, getting away
- Eight of Swords: feeling trapped, restriction, self-doubt, helplessness
- Nine of Swords: anxiety, worry, sleepless nights, fear
- Ten of Swords: painful ending, hitting bottom, release, a new dawn
- Page of Swords: curiosity, new ideas, vigilance, communication
- Knight of Swords: ambition, fast thinking, drive, haste
- Queen of Swords: clear thinking, independence, honesty, perception
- King of Swords: intellect, authority, truth, clear judgement

## Pentacles

- Ace of Pentacles: new opportunity, prosperity, a solid start, abundance
- Two of Pentacles: balance, juggling priorities, adaptability, flexibility
- Three of Pentacles: teamwork, collaboration, craftsmanship, learning
- Four of Pentacles: saving, security, holding on, control
- Five of Pentacles: hardship, insecurity, feeling left out, worry
- Six of Pentacles: generosity, giving and receiving, sharing, fairness
- Seven of Pentacles: patience, long-term view, investment, assessment
- Eight of Pentacles: diligence, skill, practice, attention to detail
- Nine of Pentacles: independence, self-sufficiency, comfort, reward
- Ten of Pentacles: legacy, family, long-term success, stability
- Page of Pentacles: ambition, study, a new goal, diligence
- Knight of Pentacles: hard work, routine, reliability, steady progress
- Queen of Pentacles: practicality, nurturing, comfort, security
- King of Pentacles: wealth, abundance, discipline, security
