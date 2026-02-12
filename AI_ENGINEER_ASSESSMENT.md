# AI Engineer Assessment — Document Translator

**Duration:** ~3 days

---

## The Challenge

Build the best possible AI-powered document translation tool you can.

**Input:** A file + a target language
**Output:** The same file, translated

---

## Minimum Viable Product

A web interface that:
1. Accepts PDF uploads
2. Translates the content using an OpenAI Agent SDK
3. Outputs a translated PDF

Everything beyond this is up to you.

---

## Hard Requirements

| Requirement          | Details                                                                                             |
| -------------------- | --------------------------------------------------------------------------------------------------- |
| **Backend**          | Python + FastAPI                                                                                    |
| **AI**               | OpenAI Agents SDK (`openai-agents`)                                                                 |
| **Frontend**         | Your choice                                                                                         |
| **Delivery**         | Git repo with `docker compose up` that works anywhere                                               |
| **PROMPTS.md**       | Log of **all** AI prompts used during development                                                   |
| **README.md**        | Explain your agent architecture and why you made those choices                                      |
| **RETROSPECTIVE.md** | A simple document answering the question "If you had to start over, what would you do differently?" |

---

## API Key

(See the email for the API key)

Budget is generous, but manage development costs. The strategy is to keep the costs low while building and to use more expensive models when necessary or verifying the quality of the translation.

---

## Resources

Please take the time to familiarize yourself with this library:
- **OpenAI Agents SDK:** https://github.com/openai/openai-agents-python
- **OpenAI Agents Docs:** https://openai.github.io/openai-agents-python/

---

## What We're Evaluating

### 1. Agency
Your capacity to make decisions and push the project as far as possible. We're not giving you a checklist — show us what you think a great document translator looks like.

### 2. AI Engineering
Demonstrate excellent understanding of:
- AI Agents and orchestration
- Tool calling
- MCP servers (building and/or using)
- Prompt engineering
- Agent handoffs
- Error handling and retries

### 3. User Experience
Thoughtful decisions that make the interface genuinely good:
- Branded for **Stark** (find some branding online)
- Intuitive and user-friendly
- Clear feedback during translation
- Graceful error handling

### 4. Your Reasoning
We want to see how you think, not just what you built:
- **All prompts documented** in PROMPTS.md — including failed attempts
- **Architecture decisions explained** in the README.md

---

## Ideas to Explore

Not a checklist. Pick what makes sense, ignore what doesn't, add your own.

- Support more formats: Word, Excel, PowerPoint, HTML, Markdown...
- Preserve formatting, styles, tables, images
- Agent execution tracing / observability
- Multiple target languages at once
- Translation memory / glossary
- Progress tracking with real-time updates
- Side-by-side preview (original vs translated)
- Batch processing (multiple files)
- Translation history
- Edit translations before download
- Build an MCP server (e.g., make it possible to translate files from Cursor)
- Connect MCP tools to your agents
- Auto-detect source language
- Handle edge cases: scanned PDFs, large files, complex layouts
- Quality validation agent

---

## Questions to Consider

These will shape your architecture. Think about them early.

- How do you approach translating a large document that doesn't fit in a single context window?
- How do you make translation as fast as possible?
- How do you chose between a single agent or multi-agent architecture?
- How would you add support for a new file format in 10 minutes? Is your design extensible?
- What happens when a user uploads an unsupported or corrupted file?

---

## How We Test

We will:
1. Clone your repo
2. Run `docker compose up --build`
3. Go though the features you describe in the README and test them.

---

## Before Submitting

- [ ] Fresh `git clone` works
- [ ] `docker compose up --build` runs without errors
- [ ] Upload a PDF → get a translated PDF back
- [ ] PROMPTS.md exists and is complete
- [ ] README includes a testing guide
- [ ] No secrets committed to the repo
- [ ] .env.example provided

---

## What Impresses Us

- Proper Agent orchestration
- Observability of agents (tracing, logging)
- Thoughtful loading states and progress feedback
- Security considerations (file validation, input sanitization)
- Performance thinking (parallelization, caching, async processing)
- Creative use of MCP
- Any tests at all

---

## Tips

- Document your prompts honestly. Failed attempts are interesting.
- Explain your architecture and design choices.
- Make it feel polished. Details matter.

---

## Submission

1. Push to a Git repository
2. Send us the repository URL

---

**Show us what you can do.**
