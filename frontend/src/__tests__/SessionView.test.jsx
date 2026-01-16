import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import SessionView from "../pages/SessionView.jsx";

vi.mock("../api/client", () => ({
  resolveTurn: vi.fn(),
  exportSession: vi.fn(),
  fetchThreads: vi.fn(() => Promise.resolve([])),
  fetchClocks: vi.fn(() => Promise.resolve([])),
  importSession: vi.fn(),
  respawnCharacter: vi.fn(),
  restartSession: vi.fn()
}));

import { resolveTurn } from "../api/client";

const baseSession = {
  id: 1,
  metadata: { era: "Space" }
};

const baseCharacter = {
  id: 101,
  name: "Android Bounty Hunter",
  race_id: 1,
  profession_id: 2,
  attributes_json: {
    scores: { CON: 1, DEX: 1, CHA: 0, WIS: 0, INT: 2 },
    derived: { hp: 8, ap: 2, armor_rating: 12, initiative_bonus: 1 },
    resources: { actions: 1, reactions: 1 }
  },
  statuses_json: {}
};

function renderSessionView(state) {
  return render(
    <MemoryRouter
      initialEntries={[
        { pathname: "/session/1", state }
      ]}
    >
      <Routes>
        <Route path="/session/:sessionId" element={<SessionView />} />
      </Routes>
    </MemoryRouter>
  );
}

test("session page renders", () => {
  renderSessionView({ session: baseSession, character: baseCharacter });
  expect(screen.getByText("Session #1")).toBeInTheDocument();
  expect(screen.getByText("Character Sheet")).toBeInTheDocument();
});

test("submit turn calls resolveTurn", async () => {
  resolveTurn.mockResolvedValue({
    outcome: { narration: "Test narration.", death: false },
    rolls: [],
    state_diff: { character: { resources: { actions: 0 } } }
  });
  renderSessionView({ session: baseSession, character: baseCharacter });

  fireEvent.change(screen.getByPlaceholderText("Describe your action..."), {
    target: { value: "Attack" }
  });
  fireEvent.click(screen.getByText("Send"));

  await waitFor(() => {
    expect(resolveTurn).toHaveBeenCalledWith({
      session_id: 1,
      player_text: "Attack"
    });
  });
});

test("sheet updates from turn state", async () => {
  resolveTurn.mockResolvedValue({
    outcome: { narration: "Updated.", death: false },
    rolls: [],
    state_diff: {
      character: { hp: 3, ap: 1, statuses: { Bleeding: { level: 2 } } }
    }
  });
  renderSessionView({ session: baseSession, character: baseCharacter });

  fireEvent.change(screen.getByPlaceholderText("Describe your action..."), {
    target: { value: "Attack" }
  });
  fireEvent.click(screen.getByText("Send"));

  await waitFor(() => {
    expect(screen.getByText("3 / 1")).toBeInTheDocument();
    expect(screen.getByText("Bleeding")).toBeInTheDocument();
  });
});
