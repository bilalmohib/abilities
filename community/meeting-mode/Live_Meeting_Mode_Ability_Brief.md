# Live Meeting Mode — Ability Developer Brief

**Ability Name:** meeting_mode

**Status:** Not Started — REQUIRES RESEARCH PHASE BEFORE BUILDING

**Difficulty:** Advanced (novel pattern, significant unknowns)

**Estimated Size:** 400-500 lines

**API Dependency:** None required for core (transcription + notes). Optional: Gmail API (via Composio) for emailing notes.

**File Storage:** Yes — meeting_notes_{timestamp}.json (persistent, one per meeting), meeting_mode_prefs.json (persistent, user preferences)

**Key Pattern:** Passive listening loop — the ability sits quietly, captures all speech via continuous transcription, and accumulates a running transcript that gets summarized into structured meeting notes on exit.

---

## ⚠️ THIS ABILITY REQUIRES A RESEARCH / TESTING PHASE

Unlike the other briefs, this ability uses OpenHome's SDK in a way that hasn't been validated yet. The standard pattern is conversational: speak → listen → respond → repeat. Meeting Mode flips this — it listens passively and continuously, capturing ambient room audio without responding. Multiple technical unknowns must be answered before the full build.

**See the "Contractor Research Tasks" section before writing any production code.**

---

## What This Ability Does

The user activates Meeting Mode before or during a meeting. The device sits with an open mic and passively captures everything said in the room. When the meeting ends (user says "stop" or a timer expires), the ability:

1. Generates structured meeting notes (summary, key topics, action items, decisions)
2. Offers to email the notes to the user
3. Saves the notes for later recall ("What happened in my last meeting?")
4. Can provide live insights on request during the meeting ("What's been discussed so far?")

**This is a notepad that listens, not a participant.** The ability should NOT speak during the meeting unless the user explicitly asks it something (like "what's been covered so far?"). The whole point is to be invisible to other meeting participants.

---

## Why This Is an Ability

The base LLM cannot listen to a meeting. This Ability uses OpenHome's STT pipeline in a continuous passive loop, accumulates a transcript via file storage, and uses the LLM to generate structured notes. Persistent storage enables cross-session recall of past meetings.

---

## ⚠️ Contractor Research Tasks — DO THESE FIRST

Before writing production code, the contractor must build small test abilities to answer these questions. Document findings for each.

### Research Task 1: Continuous Transcription Behavior

**Question:** How does `user_response()` and `wait_for_complete_transcription()` behave when called in a tight loop for extended periods?

**Test:** Build a minimal ability that:
```python
async def test_continuous_listen(self):
    await self.capability_worker.speak("Starting continuous listen test.")
    chunks = []
    start_time = time.time()

    while time.time() - start_time < 120:  # 2-minute test
        transcript = await self.capability_worker.user_response()
        if transcript:
            chunks.append({
                "time": time.time() - start_time,
                "text": transcript
            })
            self.worker.editor_logging_handler.info(f"Chunk: {transcript}")

    self.worker.editor_logging_handler.info(f"Total chunks: {len(chunks)}")
    await self.capability_worker.speak(f"Captured {len(chunks)} speech segments in 2 minutes.")
    self.capability_worker.resume_normal_flow()
```

**Document:**
- Does `user_response()` block indefinitely waiting for speech, or does it timeout and return empty?
- How long is each "chunk"? Does it capture one sentence? One phrase? One word?
- What happens during silence (nobody speaking for 10-30 seconds)?
- Does `wait_for_complete_transcription()` behave differently (longer chunks)?
- Any errors or disconnects during the 2-minute test?

**Then extend to 10 minutes, 30 minutes, 60 minutes.** Does behavior degrade over time?

### Research Task 2: Ambient Audio Quality

**Question:** How well does the STT pipeline handle ambient room audio vs. direct close-mic speech?

**Test:** Run the continuous listen test in different scenarios:
- User speaking directly into the device mic (baseline)
- User speaking from 3 feet away
- Two people having a conversation near the device
- Multiple people talking over each other
- Background noise (TV, music, office chatter)

**Document:**
- Transcription accuracy at each distance/scenario
- Does the STT pipeline pick up multiple speakers or just the loudest?
- Any speaker diarization (labeling who said what)? Almost certainly NOT, but verify.
- Does the platform's noise filter (from Main Flow) interfere? If yes, does Meeting Mode need to disable it somehow?

### Research Task 3: Transcript Accumulation Limits

**Question:** How much transcript text can we accumulate before hitting practical limits?

**Test:** Simulate a 30-minute meeting by feeding text chunks into a list and periodically passing them to `text_to_text_response()` for summarization.

**Document:**
- At what transcript length does the LLM start losing context or producing worse summaries?
- How many tokens can `text_to_text_response()` handle in a single call (prompt + history)?
- Does passing very long prompts cause timeouts or errors?

**This determines the "rolling summary" strategy** — whether we need to periodically summarize accumulated transcript to keep the working context manageable.

### Research Task 4: Exit Word and Wake Phrase Detection During Passive Mode

**Question:** Can the ability reliably detect the wake phrase "hey openhome" and exit commands while in passive listen mode?

**Test:** In the continuous loop, check each transcript chunk for the wake prefix and exit phrases:
```python
WAKE_PREFIX = "hey openhome"
EXIT_PHRASES = ["end meeting", "stop meeting mode", "meeting over"]

for chunk in captured_chunks:
    chunk_lower = chunk.lower()
    if WAKE_PREFIX in chunk_lower:
        log(f"WAKE detected: {chunk}")
    for phrase in EXIT_PHRASES:
        if phrase in chunk_lower:
            log(f"EXIT detected: {chunk}")
```

**Document:**
- How consistently does the STT transcribe "hey openhome" as those exact words? What variations appear? ("hey open home", "a open home", "hey open homes", etc.)
- Try alternative wake phrases and document STT accuracy for each: "hey assistant," "meeting check," "note taker," "hey meeting mode." Which transcribes most reliably?
- False positive rate — does normal meeting conversation ever produce text matching the wake phrase?
- Does the STT reliably transcribe "end meeting" as those exact words?
- False positive rate for exit phrases — does "we should stop meeting on Fridays" trigger exit detection?
- Test with different speakers (male/female, different accents) — does wake phrase detection degrade?
- Can the user whisper the wake phrase (to be discreet) and still have it transcribed correctly?

**This test determines the wake phrase for production.** Choose whichever phrase transcribes most consistently across speakers and conditions.

### Research Task 5: Audio Recording as Alternative/Supplement

**Question:** Can `start_audio_recording()` run for extended periods (30-60 min)?

**Test:**
```python
self.capability_worker.start_audio_recording()
await self.worker.session_tasks.sleep(300)  # 5 minutes
self.capability_worker.stop_audio_recording()
wav_data = self.capability_worker.get_audio_recording()
length = self.capability_worker.get_audio_recording_length()
self.worker.editor_logging_handler.info(f"Recorded {length}, size: {len(wav_data)} bytes")
```

**Document:**
- Max recording duration before errors or memory issues?
- WAV file size for 5, 10, 30, 60 minutes?
- Can we save the WAV via file storage API? (Size limits?)
- Could we use an external STT API (Whisper, Deepgram) on the WAV for better transcription? (Future enhancement)

### Research Task 6: Gmail Email Send (If Building Email Feature)

**Question:** Can we send email via Composio using the same pattern as the Gmail Connector?

**Test:** Reuse the Phase 0 debug pattern from the Gmail Connector brief. Test `GMAIL_SEND_EMAIL` via Composio to send a simple text email to the user's own address.

**Document:**
- Working Composio slug for sending email
- Request format and required fields
- Whether we can send HTML-formatted email (for nicer meeting notes)

---

## Architecture — Based on Research Outcomes

The architecture depends on which approach works best. Here are the two primary strategies:

### Strategy A: Transcription Loop (Preferred)

Continuously call `user_response()` or `wait_for_complete_transcription()` in a loop. Accumulate transcript as text. Periodically compress via LLM summarization to manage context window.

```
Meeting Mode activated
    ↓
[PASSIVE LISTEN LOOP]
    ↓
    wait_for_complete_transcription()  ←→  returns text chunk
    ↓
    Append chunk to transcript buffer (with timestamp)
    ↓
    Check for exit phrase → if found, break
    ↓
    Check for mid-meeting query ("what's been covered?") → if found, respond
    ↓
    Every N chunks or M minutes: run rolling summary to compress old transcript
    ↓
    Loop back
    ↓
[EXIT]
    ↓
    Generate final meeting notes from full transcript + rolling summaries
    ↓
    Save to persistent storage
    ↓
    Offer to email notes
    ↓
    resume_normal_flow()
```

### Strategy B: Audio Recording + Post-Processing

Use `start_audio_recording()` to capture raw audio for the entire meeting. On exit, transcribe the full recording via external STT API, then generate notes.

**Pros:** Cleaner audio capture, no dependency on real-time STT loop behavior, could use a better STT engine post-hoc.
**Cons:** No mid-meeting insights possible (audio is just bytes until processed), requires external STT API, large file sizes, no real-time feedback.

### Strategy C: Hybrid (Best of Both)

Run BOTH simultaneously:
- Transcription loop for real-time note-taking and mid-meeting queries
- Audio recording as backup for post-meeting re-processing if needed

**This is likely the best approach, but only if Research Task 5 confirms audio recording works for extended durations.**

---

## High-Level Flow

```
MeetingModeCapability (class)
|
|-- call()                              entry point
|-- run()                               main async method
|   |-- load_prefs()                    load meeting_mode_prefs.json
|   |-- confirm_start()                "Starting meeting mode. I'll listen quietly."
|   |-- start_meeting()
|   |   |-- [optional] start_audio_recording()  background audio capture
|   |   |-- passive_listen_loop()       main transcription capture loop
|   |       |-- capture chunk
|   |       |-- check for exit phrase
|   |       |-- check for mid-meeting query
|   |       |-- append to transcript
|   |       |-- periodic rolling summary (every 5-10 min)
|   |
|   |-- end_meeting()
|   |   |-- [optional] stop_audio_recording()
|   |   |-- generate_meeting_notes()    LLM: full transcript → structured notes
|   |   |-- save_notes()               persistent storage
|   |   |-- speak_summary()            brief verbal summary
|   |   |-- offer_email()              "Want me to email these notes?"
|   |   |-- [if yes] send_email()      via Gmail/Composio
|   |
|   |-- resume_normal_flow()
|
|-- Transcript management
|   |-- append_chunk()                  add timestamped text to buffer
|   |-- rolling_summary()              compress old chunks to stay within limits
|   |-- get_full_transcript()          combine summaries + recent chunks
|
|-- Note generation
|   |-- generate_meeting_notes()        LLM: transcript → structured notes
|   |-- format_notes_for_speech()       voice-friendly summary
|   |-- format_notes_for_email()        formatted text/HTML for email
|
|-- Recall
|   |-- recall_meeting()               "What happened in my last meeting?"
|   |-- search_meetings()             "Did anyone mention the budget?"
|
|-- Email
|   |-- send_notes_email()             Composio/Gmail API
```

### State During a Session

```python
self.transcript_chunks = []      # Raw timestamped transcript chunks
self.rolling_summaries = []      # Compressed summaries of older chunks
self.meeting_start_time = None   # When the meeting started
self.chunk_count = 0             # Total chunks captured
self.is_recording = False        # Whether audio recording is active
self.prefs = {}                  # User preferences
```

---

## Transcript Management — The Rolling Summary Pattern

This is the critical technical challenge. A 30-minute meeting could produce 5,000-10,000 words of transcript. You cannot pass all of that to the LLM in one shot — it will exceed context limits and quality will degrade.

### The Rolling Window

Maintain two buffers:
1. **Rolling summaries:** Compressed summaries of older transcript segments (each ~200-300 words covering 5-10 minutes of meeting)
2. **Recent chunks:** The last N minutes of raw transcript (for detail and recency)

```python
ROLLING_SUMMARY_INTERVAL = 300   # Summarize every 5 minutes
MAX_RECENT_CHUNKS_CHARS = 8000   # Keep ~8000 chars of recent raw transcript
SUMMARY_CHUNK_SIZE = 5           # Number of minutes per summary chunk

async def maybe_run_rolling_summary(self):
    """Check if it's time to compress older transcript into a summary."""
    elapsed = time.time() - self.meeting_start_time
    summaries_expected = int(elapsed / ROLLING_SUMMARY_INTERVAL)

    if summaries_expected > len(self.rolling_summaries):
        # Time to summarize the oldest un-summarized chunks
        unsummarized_text = self.get_unsummarized_chunks()

        if len(unsummarized_text) > 500:  # Only summarize if there's enough content
            summary = self.capability_worker.text_to_text_response(
                f"Summarize these meeting transcript segments into 2-3 concise paragraphs. "
                f"Preserve key decisions, action items, names, and numbers:\n\n{unsummarized_text}",
                system_prompt="You are a meeting notes assistant. Be concise but thorough. "
                              "Capture WHO said WHAT, any DECISIONS made, and ACTION ITEMS assigned."
            )

            self.rolling_summaries.append({
                "time_range": f"{len(self.rolling_summaries) * 5}-{(len(self.rolling_summaries) + 1) * 5} min",
                "summary": summary
            })

            # Clear the summarized chunks from the recent buffer
            self.trim_old_chunks()

            self.worker.editor_logging_handler.info(
                f"Rolling summary #{len(self.rolling_summaries)} generated"
            )
```

### Building Full Context for Queries

When the user asks "what's been discussed?" or when generating final notes:

```python
def build_full_context(self) -> str:
    """Build the complete meeting context from summaries + recent chunks."""
    parts = []

    # Include all rolling summaries
    for summary in self.rolling_summaries:
        parts.append(f"[{summary['time_range']}]\n{summary['summary']}")

    # Include recent raw transcript
    recent_text = self.get_recent_chunks_text()
    if recent_text:
        elapsed = int((time.time() - self.meeting_start_time) / 60)
        parts.append(f"[Recent ({elapsed} min mark)]\n{recent_text}")

    return "\n\n---\n\n".join(parts)
```

---

## The Passive Listen Loop

The core loop must be SILENT — no speaking unless spoken to.

```python
EXIT_PHRASES = [
    "end meeting", "stop meeting mode", "meeting over",
    "stop recording", "end meeting mode"
]

# Mid-meeting queries now REQUIRE wake prefix — no loose phrase matching
WAKE_PREFIX = "hey openhome"  # Configurable in prefs

# Decide if this is an ability-directed query or just meeting chatter
# ONLY called after Gate 1 (wake prefix) passes
MEETING_COMMAND_CONFIRM_PROMPT = """You are a meeting assistant running in silent mode.
The wake phrase "{wake_prefix}" was detected in this captured speech:

"{transcript_chunk}"

Determine if this is GENUINELY a command directed at the meeting assistant,
or if the wake phrase appeared coincidentally in normal conversation.

Return ONLY a JSON object:
{{"is_command": true|false, "command_type": "query"|"exit"|"none", "confidence": 0.0 to 1.0}}

Be EXTREMELY conservative. A false positive means the assistant will speak out loud
during a live meeting, embarrassing the user in front of colleagues or clients.
If there is ANY doubt, return false.
"""

# Exit classification — used when exit phrases detected WITHOUT wake prefix
EXIT_CONFIRM_PROMPT = """A meeting assistant is listening to a live meeting.
It detected a potential exit phrase in this captured speech:

"{transcript_chunk}"

Is the speaker commanding the assistant to END the meeting recording?
Or are they just talking about meetings in general?

Return ONLY: {{"is_exit": true|false, "confidence": 0.0 to 1.0}}

Examples that ARE exit commands:
- "End meeting" (standalone)
- "Stop meeting mode"
- "Meeting over, thanks OpenHome"

Examples that are NOT exit commands:
- "We should stop meeting about this every week"
- "Let's end the meeting with a vote on this"
- "The meeting's almost over, let's wrap up the budget item"
- "I think this meeting is over-scheduled"

If the phrase is part of a longer sentence about something else, return false.
"""
```

### The Loop

```python
async def passive_listen_loop(self):
    """Main passive listening loop — captures ambient speech SILENTLY."""
    self.worker.editor_logging_handler.info("[MeetingMode] Entering passive listen loop")
    last_summary_time = time.time()
    wake_prefix = self.prefs.get("wake_phrase", WAKE_PREFIX).lower()

    while True:
        # Capture next speech chunk
        chunk = await self.capability_worker.wait_for_complete_transcription()

        if not chunk or len(chunk.strip()) < 3:
            # Empty or noise — skip
            continue

        timestamp = time.time() - self.meeting_start_time
        self.worker.editor_logging_handler.info(
            f"[MeetingMode] [{int(timestamp)}s] Captured: {chunk[:80]}..."
        )

        chunk_lower = chunk.lower()

        # =====================================================
        # GATE 1: Check for wake prefix (mid-meeting queries)
        # Without wake prefix, ALL speech is just transcript.
        # =====================================================
        if wake_prefix in chunk_lower:
            self.worker.editor_logging_handler.info(
                f"[MeetingMode] Wake prefix detected in: {chunk[:60]}"
            )
            # GATE 2: LLM confirmation (high threshold)
            classification = self.confirm_command(chunk, wake_prefix)

            if classification.get("is_command") and classification.get("confidence", 0) > 0.85:
                cmd_type = classification.get("command_type", "query")

                if cmd_type == "exit":
                    self.worker.editor_logging_handler.info("[MeetingMode] Exit via wake command")
                    break

                if cmd_type == "query":
                    await self.handle_mid_meeting_query(chunk)
                    continue  # Don't add the query to the transcript
            else:
                self.worker.editor_logging_handler.info(
                    f"[MeetingMode] Wake prefix found but LLM rejected "
                    f"(confidence: {classification.get('confidence', 0)}). Treating as transcript."
                )

        # =====================================================
        # EXIT CHECK: Short utterances matching exit phrases
        # (No wake prefix required, but extra strict)
        # =====================================================
        word_count = len(chunk_lower.split())
        if word_count <= 6:  # Exit commands are short — long sentences are conversation
            is_potential_exit = any(phrase in chunk_lower for phrase in EXIT_PHRASES)
            if is_potential_exit:
                exit_confirmed = self.confirm_exit(chunk)
                if exit_confirmed.get("is_exit") and exit_confirmed.get("confidence", 0) > 0.85:
                    self.worker.editor_logging_handler.info("[MeetingMode] Exit phrase confirmed")
                    break
                else:
                    self.worker.editor_logging_handler.info(
                        f"[MeetingMode] Exit phrase found but rejected "
                        f"(confidence: {exit_confirmed.get('confidence', 0)})"
                    )

        # =====================================================
        # DEFAULT: Everything else is transcript — add silently
        # =====================================================
        self.transcript_chunks.append({
            "timestamp": round(timestamp, 1),
            "text": chunk
        })
        self.chunk_count += 1

        # Periodic rolling summary
        if time.time() - last_summary_time > ROLLING_SUMMARY_INTERVAL:
            await self.maybe_run_rolling_summary()
            last_summary_time = time.time()

        # Save transcript to session file periodically (crash recovery)
        if self.chunk_count % 10 == 0:
            await self.save_session_transcript()
```

### Mid-Meeting Queries

When the user asks "what's been covered so far?" the ability briefly breaks silence:

```python
async def handle_mid_meeting_query(self, query: str):
    """Handle a mid-meeting question from the user."""
    self.worker.editor_logging_handler.info(f"[MeetingMode] Mid-meeting query: {query}")

    context = self.build_full_context()

    response = self.capability_worker.text_to_text_response(
        f"The user asked: {query}\n\nMeeting context so far:\n{context}",
        system_prompt="You are a meeting assistant. Answer the user's question based on "
                      "the meeting transcript. Be brief — you're interrupting a live meeting. "
                      "2-3 sentences max. If asked for action items, list them concisely."
    )

    await self.capability_worker.speak(response)
    # After speaking, go back to silent listening
```

---

## Meeting Notes Generation

When the meeting ends, generate structured notes:

```python
MEETING_NOTES_PROMPT = """You are a professional meeting notes generator.
Generate structured meeting notes from this transcript.

Meeting duration: {duration} minutes
Transcript:
{full_context}

Return a JSON object:
{{
    "title": "Brief meeting title inferred from discussion topics",
    "duration_minutes": {duration},
    "summary": "2-3 paragraph summary of the meeting's key points",
    "topics_discussed": [
        "Topic 1: brief description",
        "Topic 2: brief description"
    ],
    "key_decisions": [
        "Decision 1",
        "Decision 2"
    ],
    "action_items": [
        {{"assignee": "Person name or 'Unassigned'", "task": "What needs to be done", "deadline": "If mentioned, otherwise null"}},
    ],
    "insights": [
        "Notable observation 1 (e.g., 'The budget discussion took up 60% of the meeting')",
        "Notable observation 2 (e.g., 'Three different timelines were proposed but none confirmed')"
    ],
    "participants_mentioned": ["Name 1", "Name 2"],
    "follow_up_needed": "Brief note on next steps or follow-up meeting if discussed"
}}

Rules:
- Only include information that was actually discussed. Do not fabricate.
- Action items should be specific and actionable, not vague.
- If you can't determine who said something, attribute it to "Unknown speaker."
- Insights should be genuinely useful observations, not filler.
- participants_mentioned should only include names explicitly spoken during the meeting.
"""
```

### Spoken Summary (Brief — User Can Read Full Notes Later)

```python
def format_notes_for_speech(self, notes: dict) -> str:
    """Create a brief spoken summary of the meeting notes."""
    parts = []

    title = notes.get("title", "your meeting")
    duration = notes.get("duration_minutes", 0)
    parts.append(f"Here's a summary of {title}. The meeting lasted about {duration} minutes.")

    # Key topics (max 3)
    topics = notes.get("topics_discussed", [])
    if topics:
        topic_str = ", ".join(topics[:3])
        parts.append(f"Main topics: {topic_str}.")

    # Action items count
    actions = notes.get("action_items", [])
    if actions:
        parts.append(f"There are {len(actions)} action items.")
        # Speak first 2
        for item in actions[:2]:
            assignee = item.get("assignee", "Someone")
            task = item.get("task", "")
            parts.append(f"{assignee} needs to {task}.")
        if len(actions) > 2:
            parts.append(f"Plus {len(actions) - 2} more.")

    # Key decisions
    decisions = notes.get("key_decisions", [])
    if decisions:
        parts.append(f"{len(decisions)} decision{'s' if len(decisions) > 1 else ''} made.")

    return " ".join(parts)
```

### Formatted Notes for Email / Storage

```python
def format_notes_for_email(self, notes: dict) -> str:
    """Format meeting notes as readable text for email."""
    lines = []
    lines.append(f"MEETING NOTES: {notes.get('title', 'Untitled Meeting')}")
    lines.append(f"Duration: {notes.get('duration_minutes', '?')} minutes")
    lines.append(f"Date: {self.today_str}")
    lines.append("")

    lines.append("SUMMARY")
    lines.append(notes.get("summary", "No summary available."))
    lines.append("")

    topics = notes.get("topics_discussed", [])
    if topics:
        lines.append("TOPICS DISCUSSED")
        for topic in topics:
            lines.append(f"  - {topic}")
        lines.append("")

    decisions = notes.get("key_decisions", [])
    if decisions:
        lines.append("KEY DECISIONS")
        for decision in decisions:
            lines.append(f"  - {decision}")
        lines.append("")

    actions = notes.get("action_items", [])
    if actions:
        lines.append("ACTION ITEMS")
        for item in actions:
            assignee = item.get("assignee", "Unassigned")
            task = item.get("task", "")
            deadline = item.get("deadline")
            deadline_str = f" (by {deadline})" if deadline else ""
            lines.append(f"  [ ] {assignee}: {task}{deadline_str}")
        lines.append("")

    insights = notes.get("insights", [])
    if insights:
        lines.append("INSIGHTS")
        for insight in insights:
            lines.append(f"  - {insight}")
        lines.append("")

    follow_up = notes.get("follow_up_needed")
    if follow_up:
        lines.append("FOLLOW-UP")
        lines.append(f"  {follow_up}")

    return "\n".join(lines)
```

---

## Meeting Recall — Cross-Session Memory

Saved meeting notes can be recalled later.

### Storage Format

Each meeting is saved as a separate file: `meeting_notes_{YYYYMMDD}_{HHMMSS}.json`

```json
{
    "title": "Q1 Budget Planning",
    "date": "2026-02-17",
    "start_time": "14:30",
    "duration_minutes": 45,
    "summary": "...",
    "topics_discussed": ["..."],
    "key_decisions": ["..."],
    "action_items": [{"assignee": "...", "task": "...", "deadline": "..."}],
    "insights": ["..."],
    "participants_mentioned": ["..."],
    "follow_up_needed": "...",
    "full_transcript_preview": "First 2000 chars of raw transcript for search..."
}
```

**Also maintain a meeting index file** — `meeting_index.json` — that lists all saved meetings for fast search without loading every file:

```json
{
    "meetings": [
        {
            "filename": "meeting_notes_20260217_143000.json",
            "title": "Q1 Budget Planning",
            "date": "2026-02-17",
            "duration_minutes": 45,
            "participants": ["Sarah", "John", "Marcus"],
            "topic_keywords": ["budget", "Q1", "planning", "headcount"]
        }
    ]
}
```

### Recall Queries

```
User: "What happened in my last meeting?"
→ Load most recent meeting from index, speak summary.

User: "Did anyone mention the budget in a meeting?"
→ Search meeting index keywords + transcript previews, speak matches.

User: "What were the action items from the meeting with Sarah?"
→ Filter by participant, load matching meeting, speak action items.
```

### Recall Prompt

```
RECALL_PROMPT = """You are searching saved meeting notes based on a user's voice query.

Available meetings:
{meeting_index}

User's query: {user_input}

Return ONLY a JSON object:
{{
    "matching_filenames": ["filename1.json", "filename2.json"],
    "search_type": "latest" | "by_person" | "by_topic" | "by_date",
    "what_to_read": "summary" | "action_items" | "decisions" | "full"
}}
"""
```

---

## Email Integration (Optional)

After generating notes, offer to email them:

```python
async def offer_email(self, notes: dict):
    """Offer to email the meeting notes to the user."""
    confirmed = await self.capability_worker.run_confirmation_loop(
        "Want me to email you these meeting notes?"
    )

    if not confirmed:
        await self.capability_worker.speak("Got it. Notes are saved, you can ask for them anytime.")
        return

    # Format for email
    email_body = self.format_notes_for_email(notes)
    subject = f"Meeting Notes: {notes.get('title', 'Meeting')} - {self.today_str}"

    await self.capability_worker.speak("Sending the notes to your email now.")

    # Use Composio Gmail (same pattern as Gmail Connector)
    success = self.send_email(subject, email_body)

    if success:
        await self.capability_worker.speak("Notes sent to your email.")
    else:
        await self.capability_worker.speak(
            "I couldn't send the email right now, but the notes are saved. "
            "You can ask me to recall them anytime."
        )
```

**Implementation note:** The email send pattern is identical to the Gmail Connector brief. Use the same Composio `GMAIL_SEND_EMAIL` slug (or `GMAIL_SEND_EMAIL` — test in Phase 0 of the Gmail Connector). The contractor should NOT build a separate email system — share the pattern.

**Who receives the email?** The user's own email address. This should be stored in meeting_mode_prefs.json or pulled from the connected Gmail account via Composio. On first use, ask the user: "What email should I send meeting notes to?"

---

## Insights — The "Smart" Meeting Assistant

Beyond raw notes, the LLM can provide meeting insights. These are generated at the end of the meeting as part of the notes, and can also be requested mid-meeting.

### Types of Insights

```python
INSIGHTS_PROMPT = """You are analyzing a meeting transcript for useful insights.

Meeting transcript:
{full_context}

Generate 2-4 genuinely useful observations. Examples of good insights:
- "The team discussed 3 different launch timelines but didn't commit to any. A decision is needed."
- "Sarah raised a concern about budget twice. This seems unresolved."
- "The first 20 minutes were spent recapping last week — consider starting with a written summary next time."
- "5 action items were assigned but none have deadlines. Consider adding target dates."

Bad insights (avoid these):
- "The meeting covered several topics." (too vague)
- "Everyone contributed to the discussion." (meaningless)
- Generic observations that don't help anyone

Return as a JSON list of strings:
["insight 1", "insight 2", "insight 3"]
"""
```

### Mid-Meeting "Check-In"

The user can ask for a live status during the meeting — but ONLY with the wake prefix:

```
User: "Hey OpenHome, what have we covered so far?"
Ability: "So far you've discussed the Q1 budget breakdown, headcount for the engineering
team, and Sarah raised a concern about vendor costs. No decisions finalized yet.
Two potential action items: John to get vendor quotes, and someone needs to schedule
the follow-up with finance."
```

This is powerful — it's like having a smart participant who's been paying perfect attention.

---

## Voice UX Rules

### SILENCE IS DEFAULT — FALSE POSITIVE PREVENTION IS THE #1 PRIORITY

The ability must NOT speak during the meeting unless directly addressed. Any unexpected TTS output would be disruptive and embarrassing in a real meeting. Imagine you're in a meeting with your boss and the device suddenly says "Here's what's been covered so far..." because someone said something that vaguely matched a query phrase. That's a product-killing moment. **Every design decision should bias toward NOT speaking.**

```
GOOD: [Passive listening... 45 minutes of silence... user says "end meeting"]
      "Meeting captured. 45 minutes, 3 topics, 5 action items. Want me to email the notes?"

BAD:  [Every 5 minutes] "I'm still listening!" (NEVER do this)
BAD:  [After capturing a chunk] "Got it." (NEVER do this)
BAD:  [Someone says "can you summarize that?" to a colleague] → Ability starts talking (DISASTER)
```

### ⚠️ CRITICAL: Minimizing False Positives During Live Meetings

**The goal is ZERO false positives.** It is far better to miss a real command (user just says it again, slightly annoyed) than to accidentally speak during a live meeting (user is embarrassed in front of colleagues, possibly in front of a client). False negatives are inconvenient. False positives are humiliating. Design accordingly.

**Rule: All mid-meeting commands MUST require a specific wake prefix.**

Do NOT respond to generic phrases like "summarize that," "what did we talk about," or "any action items" — these are things people say to EACH OTHER in meetings constantly. The ability must only respond when the user explicitly addresses it.

**Required wake prefix:** The user must say **"Hey OpenHome"** (or a configured wake phrase) before any mid-meeting command. Without the prefix, ALL captured speech is treated as transcript — no exceptions.

```
RESPONDS (wake prefix detected):
  "Hey OpenHome, what's been covered so far?"
  "Hey OpenHome, any action items?"
  "Hey OpenHome, recap the meeting"

DOES NOT RESPOND (no wake prefix — just meeting chatter):
  "Can you summarize that for the team?"
  "What have we discussed so far?"
  "Let's go over the action items"
  "We should stop meeting on Fridays"
  "Can someone take notes on this?"
```

**Exit commands are the ONE exception** — "end meeting" and "stop meeting mode" should work WITHOUT a wake prefix, because the user wants to end the session. But even these must be validated:

```
EXIT (high confidence, clearly a command):
  "End meeting"
  "Stop meeting mode"
  "Meeting over"

NOT EXIT (meeting chatter — do NOT exit):
  "We should stop meeting about this every week"
  "Let's end the meeting with a vote" (they're talking TO the group)
  "The meeting's almost over"
```

**Implementation: Two-gate system for all mid-meeting responses:**

Gate 1 — String match: Does the captured chunk contain the wake prefix "hey openhome" (or configured phrase)?
- If NO → skip, add to transcript, no further processing. Done.
- If YES → proceed to Gate 2.

Gate 2 — LLM confirmation: Is this genuinely a command directed at the assistant?
- LLM classifies with the full context of the phrase
- Only respond if confidence > 0.85 (not 0.7 — raise the bar)
- If confidence < 0.85 → add to transcript silently, log the near-miss

```python
# Gate 1: Wake prefix check (fast, no LLM call)
WAKE_PREFIX = "hey openhome"  # Configurable in prefs

def has_wake_prefix(self, chunk: str) -> bool:
    return WAKE_PREFIX in chunk.lower()

# Gate 2: LLM confirmation (only runs if Gate 1 passes)
QUERY_CONFIRM_PROMPT = """A meeting assistant heard this speech in a live meeting.
The wake phrase "{wake_prefix}" was detected in the audio.

Full captured text: "{chunk}"

Is this GENUINELY a command directed at the meeting assistant?
Or did the wake phrase appear coincidentally in normal conversation?

Return ONLY: {{"is_command": true|false, "command_type": "query"|"exit"|"none", "confidence": 0.0-1.0}}

Be VERY conservative. If there's any doubt, return false. A false positive means
the assistant will speak out loud during a live meeting, embarrassing the user.
"""

# In the listen loop:
if self.has_wake_prefix(chunk):
    classification = self.confirm_command(chunk)
    if classification.get("is_command") and classification.get("confidence", 0) > 0.85:
        await self.handle_mid_meeting_query(chunk)
        continue
# If we get here, it's just transcript — add silently
```

**Exit command handling (no wake prefix required, but extra careful):**

```python
EXIT_EXACT_PHRASES = [
    "end meeting", "stop meeting mode", "meeting over",
    "stop recording", "end meeting mode"
]

def check_exit(self, chunk: str) -> bool:
    chunk_lower = chunk.lower().strip()
    # Must be a SHORT utterance that IS the command, not part of a longer sentence
    if len(chunk_lower.split()) > 6:
        # Too long to be a standalone command — probably a sentence containing the phrase
        return False
    for phrase in EXIT_EXACT_PHRASES:
        if phrase in chunk_lower:
            # LLM double-check for borderline cases
            return self.confirm_exit(chunk)
    return False
```

**Configurable wake phrase:** Store in meeting_mode_prefs.json so users can change it:
```json
{
    "wake_phrase": "hey openhome",
    "exit_requires_confirmation": false
}
```

**Add to Research Task 4:** Test wake phrase detection reliability. How consistently does the STT transcribe "hey openhome" correctly? Try alternative phrases: "hey assistant," "meeting check," "note taker." Find the phrase that transcribes most reliably.

### Startup — Brief and Clear

```
"Meeting mode on. I'll listen quietly and take notes. Say 'end meeting' when you're done.
If you need me during the meeting, say 'Hey OpenHome' first."
```

Keep this to 2 sentences. The user is probably about to start a meeting and doesn't want a long intro.

### Shutdown — Structured, Not Chatty

```
"Meeting over. That was about 45 minutes. Main topics: budget planning, hiring timeline,
and vendor review. I captured 5 action items. Want me to email the notes?"
```

### Mid-Meeting Response — Whisper-Brief

When responding to a wake-prefix query, be extremely concise. The user is in a live meeting with other people.

```
GOOD: "Three topics so far: budget, hiring, and the vendor issue. Two action items assigned."
BAD:  "So, let me walk you through everything that's been discussed in this meeting so far..."
```

**The user must say "Hey OpenHome" first.** Without the wake prefix, these same questions are just meeting conversation and get added to the transcript silently:
```
"Hey OpenHome, what's been covered?" → Ability responds with brief summary
"What's been covered?"              → Added to transcript, no response
"Hey OpenHome, any action items?"   → Ability responds
"Let's review the action items"     → Added to transcript, no response
```

---

## Trigger Words

```json
{
    "unique_name": "meeting_mode",
    "matching_hotwords": [
        "meeting mode", "start meeting", "meeting notes",
        "take notes", "start recording", "record this meeting",
        "meeting assistant", "note taker",
        "listen to this meeting", "take meeting notes",
        "start a meeting", "begin meeting",
        "what happened in my meeting", "last meeting notes",
        "recall meeting", "meeting summary"
    ]
}
```

**Why these words:**
- Activation: "meeting mode", "start meeting", "take notes", "record this meeting"
- Recall: "what happened in my meeting", "last meeting notes", "recall meeting"
- General: "meeting assistant", "note taker"

**Note:** "Take notes" is broad. If the user has a general note-taking ability installed too, the Main Flow router needs to disambiguate. Context like "take notes on this meeting" vs. "take a note about Sarah" should route differently.

---

## Persistent Storage

### meeting_mode_prefs.json (persistent)

```json
{
    "email_address": "user@example.com",
    "auto_email": false,
    "include_insights": true,
    "include_transcript_preview": true,
    "default_max_duration_minutes": 90,
    "wake_phrase": "hey openhome",
    "exit_confidence_threshold": 0.85,
    "query_confidence_threshold": 0.85,
    "times_used": 0
}
```

### meeting_notes_{timestamp}.json (persistent, one per meeting)

Full structured notes as described in the Meeting Recall section.

### meeting_index.json (persistent, updated after each meeting)

Index of all saved meetings for fast search.

### meeting_transcript_session.json (session/temp, crash recovery)

Current meeting's raw transcript chunks. Saved periodically during the meeting. Deleted after notes are generated and saved. This is the crash recovery mechanism — if the session drops mid-meeting, the transcript isn't lost.

---

## Error Handling

```python
# Meeting start — check for obvious issues
async def start_meeting(self):
    # Verify we can listen
    await self.capability_worker.speak("Let me make sure I can hear you. Say something.")
    test = await self.capability_worker.user_response()
    if not test:
        await self.capability_worker.speak(
            "I'm having trouble hearing. Check that the microphone is working and try again."
        )
        self.capability_worker.resume_normal_flow()
        return

    await self.capability_worker.speak("Meeting mode is on. I'll listen quietly now.")
    await self.passive_listen_loop()

# Mid-meeting LLM failure
try:
    summary = self.capability_worker.text_to_text_response(prompt)
except Exception as e:
    self.worker.editor_logging_handler.error(f"LLM summarization failed: {e}")
    # Don't speak the error during a meeting — just log it
    # The rolling summary will catch up next cycle

# Session crash recovery
async def check_for_interrupted_meeting(self):
    """On startup, check if there's an unfinished meeting transcript."""
    if await self.capability_worker.check_if_file_exists("meeting_transcript_session.json", True):
        await self.capability_worker.speak(
            "It looks like a previous meeting session was interrupted. "
            "Want me to generate notes from what I captured?"
        )
        confirmed = await self.capability_worker.run_confirmation_loop("Generate notes from the interrupted session?")
        if confirmed:
            raw = await self.capability_worker.read_file("meeting_transcript_session.json", True)
            # Process interrupted transcript...

# Empty meeting
if self.chunk_count < 3:
    await self.capability_worker.speak(
        "I didn't capture much from that meeting. There isn't enough to generate notes."
    )
    self.capability_worker.resume_normal_flow()
    return

# Max duration safety net
MAX_MEETING_DURATION = 5400  # 90 minutes default
if time.time() - self.meeting_start_time > MAX_MEETING_DURATION:
    await self.capability_worker.speak(
        "We've been going for 90 minutes. I'll wrap up the notes from what I have."
    )
    break  # Exit the listen loop
```

---

## Practical Limits to Discover

The contractor should document these findings for the team:

| Question | Why It Matters | Test Method |
|----------|---------------|-------------|
| Max continuous listen duration | Defines meeting length limit | Research Task 1 |
| Transcript chunks per minute | Determines rolling summary frequency | Research Task 1 |
| STT accuracy at 3+ feet | Determines device placement guidance | Research Task 2 |
| Multi-speaker handling | Can we tell who's talking? | Research Task 2 |
| LLM context limit for summarization | Determines max transcript before compression | Research Task 3 |
| Audio recording max duration | Determines if hybrid approach is viable | Research Task 5 |
| WAV file size per minute | Storage planning | Research Task 5 |
| Exit phrase detection reliability | User experience on ending meetings | Research Task 4 |

---

## Code Quality Checklist

- resume_normal_flow() called on EVERY exit path (end of meeting, error, max duration, empty meeting)
- No print() — using editor_logging_handler
- No raw asyncio.sleep() or asyncio.create_task() — using session_tasks
- **NO SPEAKING during passive listen mode unless wake prefix "Hey OpenHome" is detected AND LLM confirms with >0.85 confidence**
- **Mid-meeting queries require wake prefix — no exceptions**
- **Exit detection uses word-count gate (≤6 words) + LLM confirmation at >0.85 confidence**
- **All near-miss detections (wake prefix found but LLM rejected) are logged for debugging**
- text_to_text_response() used WITHOUT await (synchronous)
- JSON persistence uses delete + write pattern
- check_if_file_exists() before read_file()
- Filenames namespaced: meeting_notes_*, meeting_index.json, meeting_mode_prefs.json
- Session transcript saved periodically for crash recovery
- Max duration safety net prevents runaway listening
- Rolling summary keeps LLM context manageable for long meetings
- Email send always gets explicit confirmation
- Error during meeting = log silently, don't speak (meeting is live!)
- Empty/short meetings handled gracefully (don't generate blank notes)
- Wake phrase is configurable in meeting_mode_prefs.json
- Startup message tells user the wake phrase and exit command

---

## Files to Deliver

```
meeting_mode/
    main.py           All Ability logic — single file, single class
    config.json       Trigger words and unique name
```

config.json:
```json
{
    "unique_name": "meeting_mode",
    "matching_hotwords": [
        "meeting mode", "start meeting", "meeting notes",
        "take notes", "start recording", "record this meeting",
        "meeting assistant", "note taker",
        "listen to this meeting", "take meeting notes",
        "start a meeting", "begin meeting",
        "what happened in my meeting", "last meeting notes",
        "recall meeting", "meeting summary"
    ]
}
```

---

## Build Order

**Phase 0: RESEARCH — Run all 5 research tasks.** This is non-negotiable. Build small test abilities for each research task. Document findings. Share with the team before proceeding. The architecture decisions for the full build depend on these results. Budget 3-5 days for this phase.

**Phase 1: Basic transcript capture loop.** Build the passive listen loop with `wait_for_complete_transcription()`. Capture chunks for 5 minutes. Log everything. Verify chunks are arriving and make sense. No LLM processing yet.

**Phase 2: Exit detection.** Add exit phrase detection (string match first, then LLM disambiguation). Verify the user can reliably end the meeting by voice.

**Phase 3: Meeting notes generation.** On exit, pass the accumulated transcript to the LLM. Generate structured notes JSON. Save to persistent storage. Speak the brief summary.

**Phase 4: Rolling summary.** Add the periodic rolling summary to manage long meetings. Test with 15+ minute simulated meetings. Verify notes quality doesn't degrade.

**Phase 5: Mid-meeting queries.** Add the query detection and response system. Test "what's been covered so far?" during a live capture session.

**Phase 6: Meeting recall.** Add the meeting index and recall system. "What happened in my last meeting?" Load and speak saved notes.

**Phase 7: Email integration.** Add the option to email notes via Composio/Gmail. Requires working Gmail send pattern from the Gmail Connector brief.

**Phase 8 (optional): Audio recording hybrid.** If Research Task 5 shows audio recording works for long durations, add it as a parallel capture mechanism for backup.

---

## What This Ability Is NOT

- **Not a real-time transcription display.** There's no screen to show live text. This is voice-in, voice-out.
- **Not a speaker diarization tool.** The STT pipeline almost certainly cannot distinguish Speaker A from Speaker B. Notes will attribute to "Unknown speaker" unless someone says a name before speaking.
- **Not a meeting bot that joins Zoom/Teams.** This captures audio from the physical device's microphone. It works for in-person meetings where the device is in the room. Virtual meeting recording requires different infrastructure.
- **Not an unlimited recorder.** There will be duration limits based on Research Task findings. Plan for 60-90 minutes max initially.
