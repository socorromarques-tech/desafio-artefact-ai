# Customer Support Assistant — Empório da Música

A prototype customer support assistant for Empório da Música, a musical instrument
store in Campo Grande, Mato Grosso do Sul, Brazil. The agent uses CSV product and
order data, retrieves information from the store policy PDF, and responds in
Brazilian Portuguese through the Anthropic Messages API.

> **Language choice:** The assistant responds in Brazilian Portuguese because it
> is designed for customers of a music store in Brazil. The project documentation
> and challenge submission materials are in English, as requested.

> **Submission status:** one real conversation is recorded in
> [`examples/01-catalogo-e-pagamento.md`](examples/01-catalogo-e-pagamento.md).
> After that run, an API credential issue prevented the generation of additional
> real conversations. Simulated responses have not been presented as real runs.

## Requirements

- Python 3.10 or later.
- A valid Anthropic API key and access to the configured model to run conversations
  with the LLM.
- Git to clone the repository.

Automated tests use `unittest`, which is included in the Python standard library.

## Installation and configuration

In PowerShell:

```powershell
git clone https://github.com/socorromarques-tech/desafio-artefact-ai.git
Set-Location desafio-artefact-ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set a valid API key and a model enabled for your account:

```dotenv
ANTHROPIC_API_KEY=your_real_api_key
MODEL_NAME=claude-sonnet-5-5
```

`MODEL_NAME` can be changed to another model identifier available to your account.
Do not use the retired `claude-3-5-sonnet-20241022` identifier. Never share or
commit your API key: `.env` is listed in `.gitignore`.

Optionally, set a fixed date for reproducible return-window demonstrations:

```dotenv
REFERENCE_DATE=2026-03-29
```

The format is `YYYY-MM-DD`. If omitted, the agent uses the system's local date.
Setting a fixed date makes calculations reproducible; it does not fill in missing
dates in the CSV data.

## Run the agent

With the virtual environment activated and `.env` configured:

```powershell
python agent.py
```

Enter questions at the `Cliente:` prompt. Type `sair` to end the session.
Without a valid `ANTHROPIC_API_KEY`, the agent starts without API access and explains
that it cannot select tools; this mode does **not** generate LLM responses.

## Run tests

Run the complete test suite from the repository root:

```powershell
python -m unittest discover -s tests -v
```

Tests cover catalog search and filters, Brazilian currency formatting, promotions,
PDF extraction and retrieval, return-window validation, out-of-scope prompt
instructions, and conversation/tool-call history. They do not make requests to the
Anthropic API.

## How it works

1. `data.py` loads the six CSV files from `data/` with Pandas.
2. `store_policies.py` extracts PDF text with `pypdf` and caches the pages for the
   lifetime of the process.
3. The model receives the user question and tool definitions, then selects from:
   - `buscar_produtos`: searches product names/descriptions and filters by category,
     maximum price, and stock;
   - `consultar_pedido`: requires the email address or phone number associated with
     the order before returning its details;
   - `verificar_prazo_devolucao`: verifies the customer and calculates the return
     window only when there is sufficient evidence;
   - `consultar_politicas`: returns up to three policy-manual pages relevant to the
     topic.
4. Tool results are sent back to the model, which writes the final response. Each
   user question is limited to five tool-use cycles.
5. Questions, answers, and tool results are kept in memory during the session. They
   are not persisted to a file or database.

## Technical decisions

The choices below address the challenge criteria and favor a small, testable
prototype over additional infrastructure:

### Agent framework and approach

The agent uses Anthropic tool use (function calling) to route a customer request to
one of a small set of Python functions for catalog search, order lookup, return
window checks, and policy retrieval. This is a hybrid approach: the LLM interprets
the request and writes the response, while deterministic code handles structured
filters and date calculations. Policy lookup uses lightweight, page- and
keyword-based retrieval rather than vector RAG: the source manual is only eight
pages, so a vector database would add operational complexity without a clear benefit
for this prototype. The retrieval normalizes accents, scores terms and aliases,
returns up to three relevant pages, and preserves the original policy text.

### Model and provider

The application uses the Anthropic Messages API and a configurable Claude model
(`MODEL_NAME`). Anthropic tool use provides the structured routing required by the
agent, while keeping the model identifier configurable lets the application use a
model enabled for the evaluator's account. A valid API key and model access are
required for live conversations; automated tests do not depend on either.

### Interaction interface

The interface is a command-line application. A CLI keeps setup and operation simple
and lets the challenge focus on whether the agent can select tools and answer from
the supplied data, without spending time on a separate frontend. A web or graphical
interface would be a possible follow-up, not a requirement for this prototype.

### Conversation history and persistence

Conversation messages, tool calls, and tool results are retained in process memory
for the current session so the model can use recent context. They are not written to
a file or database: persistence is not necessary for a terminal demonstration and
would introduce additional handling of potentially sensitive customer information.
History is lost when the process exits.

### Data treatment

Pandas loads the six supplied CSV files for products, categories, promotions,
orders, order items, and customers. Explicit Python filters handle category, price,
and stock rather than asking the LLM to calculate tabular results. Search
normalizes accents for Portuguese text, and currency values are presented in BRL.
The policy PDF is extracted with `pypdf`; its page text is cached for the process
lifetime and selected by keyword and alias relevance. The return-window check uses
Python date comparisons and requires an actual receipt date and online purchase
channel; an estimated delivery date is not treated as proof. Missing or conflicting
source data is reported as a limitation rather than silently inferred.

## Policies and data

The manual at `data/políticas_da_loja.pdf` covers, among other topics, business
hours, payment methods, exchanges and returns, shipping, promotions, customer
support, warranty, and privacy. It is the reference source; the agent should not
invent terms when retrieval does not find relevant information.

The CSV files include:

- `products.csv`: product names, BRL prices, categories, descriptions, stock, and
  status;
- `categories.csv`: category names and IDs;
- `promotions.csv`: product, discount, and `is_active` flag;
- `orders.csv`, `order_items.csv`, and `customers.csv`: orders, purchased items, and
  customer data used for order lookups.

The files retain their supplied names, with the
`desafio_tecnico_ai_eng -` prefix.

## Known limitations

- **Credentials and model access:** a valid Anthropic API key is required. The
  configured model must also be available to the account. The conversation in
  `examples/` was generated during an earlier run; a later attempt had no API
  connection and was not presented as a real response.
- **Examples:** the repository contains one real example, fewer than the three to
  five conversations requested in the review. A planned second conversation could
  not be generated because credentials were unavailable. The transcript records
  the observed response, not the underlying tool-call trace; the terminal does not
  currently display that trace.
- **Return eligibility:** `orders.csv` has `estimated_delivery`, but no actual
  receipt date or purchase channel. An estimate is not treated as proof of receipt,
  so the current records cannot confirm the cooling-off period. The manual also
  distinguishes online purchases.
- **Other exchange conditions:** the automated check covers only the cooling-off
  period for online purchases. It does not evaluate product condition, packaging,
  accessories, proof of purchase, exceptions, or other rights; those details should
  be checked against the policy.
- **Promotions:** the CSV has an `is_active` flag but no start or end dates. The
  agent trusts this flag and cannot validate promotion dates against a calendar.
- **Policy search:** retrieval is lexical, using predefined aliases; it is not
  vector-based semantic search. Questions phrased very differently from the PDF may
  not retrieve the expected page.
- **Conflicting contact details:** the manual lists different phone/WhatsApp
  numbers in different sections and has inconsistent email spellings. The agent
  should flag the discrepancy rather than choose a contact without confirmation
  from the store.
- **Privacy:** order verification by email/phone is a basic demo safeguard over local
  CSVs; it is not a substitute for production authentication, authorization, or
  access controls. Do not use real customer data in public examples or demos.
- **Scope:** the prompt instructs the model to refuse out-of-scope questions. Since
  refusal is an LLM instruction rather than a deterministic classifier, it cannot
  guarantee that the model will never go out of scope.
- **Catalog and context:** search returns at most ten results and supports a maximum
  price, but not a minimum price. Responses depend on the quality and freshness of
  the supplied CSV files.

## Use of AI coding assistants

An AI coding assistant was used to review the supplied feedback, implement and
review parts of the agent, create automated tests, and help prepare this
documentation. Changes were validated with local tests. The catalog/payment
conversation in `examples/` was run by the agent and provided for recording; it was
not written as though it were model output. No API key has been included in the
repository.

## Next steps if more time were available

- Generate and record three to five real conversations, including a return-policy
  question, a store-address question, and an out-of-scope question, when API access
  is available.
- Add demo logs of the tools used, without recording credentials or personal data.
- Confirm the store's official phone numbers, WhatsApp number, and email.
- Update order data with actual receipt dates and purchase channels; record
  promotion start/end dates as well.
- Implement a minimum-price filter and evaluate catalog searches in Portuguese.
- Add integration tests against a test API while keeping unit tests independent of
  network access and credentials.
