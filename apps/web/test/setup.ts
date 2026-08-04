import "@testing-library/jest-dom/vitest";

import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Each test starts from a clean DOM.
afterEach(() => cleanup());
