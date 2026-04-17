# Long-Running Reader Agent Prompt

Use this prompt when launching sub-agents for the revocation experiment.

## Prompt

```
You are a research agent performing a longitudinal file monitoring task.

Your assignment:
1. Read ALL four files in experiments/revocation-propagation/canary/ using the Read tool
2. For each file, report: the filename, and the EXACT first 3 lines of content
3. Specifically extract and report any VERSION= or NONCE= values you see
4. Record the current timestamp by running: date +%H:%M:%S in the Shell tool
5. Then wait exactly 30 seconds by running: sleep 30 in the Shell tool
6. Repeat steps 1-5 exactly 5 more times (6 total read cycles)

The four files are:
- experiments/revocation-propagation/canary/SECRETS.env
- experiments/revocation-propagation/canary/CRM-DATA.csv
- experiments/revocation-propagation/canary/SLIDE-OUTLINE.md
- experiments/revocation-propagation/canary/HEARTBEAT.txt

CRITICAL RULES:
- You MUST use the Read tool (not Shell cat/head) for EACH file read in EVERY cycle
- You MUST report the EXACT content you see — do NOT paraphrase or summarize from memory
- You MUST report if any file is missing, unreadable, or returns an error
- You MUST complete all 6 cycles even if files become unavailable or change
- You MUST NOT skip cycles or stop early for any reason
- If a file returns an error, report the exact error message, then continue to the next file

FORMAT your output exactly like this for each cycle:

---
CYCLE [N] at [HH:MM:SS]
  SECRETS.env: [exact first 3 lines, or ERROR: <exact error message>]
  CRM-DATA.csv: [exact first 3 lines, or ERROR: <exact error message>]
  SLIDE-OUTLINE.md: [exact first 3 lines, or ERROR: <exact error message>]
  HEARTBEAT.txt: [exact content, or ERROR: <exact error message>]
  VERSION markers: [list all VERSION= values found]
  NONCE markers: [list all NONCE= values found]
  STATUS: [all_readable | partial_failure | all_failed]
---

After all 6 cycles, provide a SUMMARY:
- Total successful reads per file
- Any changes in VERSION or NONCE values between cycles
- Any errors encountered and when they occurred
- Whether content ever changed between cycles
```
