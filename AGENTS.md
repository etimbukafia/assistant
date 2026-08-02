# Repository Guidelines

## Project Structure & Module Organization
`backend/` contains the FastAPI service. Startup lives in `backend/src/main.py`; app code is under `backend/src/app`, core code is under `backend/src/core`, and tests live in `backend/tests`.

`frontend/` is the Next.js App Router client. Routes live in `frontend/src/app`, UI in `frontend/src/components`, and feature logic in `hooks/`, `services/`, and `utils/`.

`mobile/` is the Expo app with screens in `mobile/app` and shared logic in `mobile/src`. Specs and assets are in `design/`, `docs/`, `plans/`, and `legal/`.

## Build, Test, and Development Commands
`cd backend && uvicorn src.main:app --reload` starts the API. `cd backend && pytest -m unit` runs tests.

`cd frontend && npm run dev` starts Next.js on port `8081`. `npm run build` creates a build, and `npm run lint` runs the Next/ESLint checks.

`cd mobile && npm run start` launches Expo. Use `npm run ios`, `npm run android`, or `npm run web` for platform targets.

`cd website && npm run dev`, `npm run build`, and `npm run lint` cover development and verification.

## Coding Style & Naming Conventions
In Python, follow the existing FastAPI route and service patterns, keep modules `snake_case`, and add type hints where practical. In TypeScript and React, keep component files in PascalCase, hooks in `useX` form, and service modules grouped by feature. Respect existing lint rules and avoid reformatting unrelated code.

## Engineering and Design Principles
Use [backend/principles.md](/C:/Users/j/afiavana/assistant/backend/principles.md) and the docs under [design/](/C:/Users/j/afiavana/assistant/design/) as working constraints. Backend and AI changes should improve workflows through speed, reliability, deterministic behavior, graceful failure paths, privacy, and user control.

UI work should reflect [design/principles.md](/C:/Users/j/afiavana/assistant/design/principles.md): one clear primary action per screen, prepared work over prompts, consistent components, and polished loading, empty, and error states. Use design tokens instead of hardcoded values and preserve the accessibility requirements in [design/accessibility_specs.md](/C:/Users/j/afiavana/assistant/design/accessibility_specs.md).

## Testing Guidelines
Backend tests use `pytest` with markers defined in `backend/pytest.ini`: `unit`, `integration`, `sandbox`, `slow`, `api`, and `live`. Name files `test_*.py`. Mobile component tests belong in `mobile/components/__tests__/`.

## Commit & Pull Request Guidelines
Recent history favors short, descriptive commit subjects such as `fixed webhook issue` and `billing implementation and settings page refactoring`. Keep commits scoped to one change.

Pull requests should state scope, link the relevant issue or context, list validation commands, and include screenshots or clips for UI work.

## Configuration Tips
Backend configuration is environment-driven; use env files where available and keep secrets out of git. The frontend expects `.env.local` values for Supabase and backend URLs.
