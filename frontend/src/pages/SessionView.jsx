import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  exportSession,
  fetchClocks,
  fetchThreads,
  importSession,
  resolveTurn,
  respawnCharacter,
  restartSession
} from "../api/client";

function useSessionState() {
  const location = useLocation();
  const params = useParams();
  const navigate = useNavigate();
  const state = location.state || {};
  const session = state.session;
  const character = state.character;

  const sessionId = session?.id || Number(params.sessionId);

  const goHome = () => navigate("/");

  return { session, character, sessionId, goHome, navigate };
}

export default function SessionView() {
  const { session, character, sessionId, goHome, navigate } = useSessionState();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [turnData, setTurnData] = useState(null);
  const [sending, setSending] = useState(false);
  const [showMechanics, setShowMechanics] = useState(false);
  const [rollEvents, setRollEvents] = useState([]);
  const [deathOpen, setDeathOpen] = useState(false);
  const [deathEntry, setDeathEntry] = useState("");
  const [devOpen, setDevOpen] = useState(false);
  const [threads, setThreads] = useState([]);
  const [clocks, setClocks] = useState([]);
  const buildSheet = (source) => {
    const attributes = source?.attributes?.scores ?? source?.attributes_json?.scores ?? {
      CON: 0,
      DEX: 0,
      CHA: 0,
      WIS: 0,
      INT: 0
    };
    const derived =
      source?.attributes?.derived ?? source?.attributes_json?.derived ?? {};
    const gear = source?.gear_pack ?? source?.gear_pack_json ?? {};
    const skills =
      source?.skill_levels ??
      source?.skill_levels_json ??
      source?.attributes?.skills ??
      source?.attributes_json?.skills ??
      {};

    return {
      attributes,
      derived,
      skills,
      inventory: Array.isArray(gear.items) ? gear.items : [],
      equipped: gear.equipped || {},
      credits: gear.credits ?? gear.starting_credits ?? 0,
      statuses: source?.statuses ?? source?.statuses_json ?? {},
      resources:
        source?.attributes?.resources ?? source?.attributes_json?.resources ?? {},
      hp: derived.hp ?? null,
      ap: derived.ap ?? null,
      ar: derived.armor_rating ?? null,
      initiative: derived.initiative_bonus ?? null
    };
  };

  const [sheetState, setSheetState] = useState(() => buildSheet(character));

  const devModeEnabled =
    session?.metadata?.settings?.dev_mode_enabled ??
    session?.metadata_json?.settings?.dev_mode_enabled ??
    false;

  const era = useMemo(
    () => session?.metadata?.era || session?.metadata_json?.era || "Space",
    [session]
  );

  const locationCard = useMemo(() => {
    const metadata = session?.metadata || session?.metadata_json || {};
    const setting = metadata.setting || {};
    const card = metadata.location_card || metadata.locationCard || {};
    const openThreads = threads.filter((thread) => thread.status === "open");
    const hooks = Array.isArray(card.hooks) && card.hooks.length
      ? card.hooks
      : openThreads.slice(0, 3).map((thread) => thread.text);
    const normalizedHooks = hooks
      .map((hook) => {
        if (typeof hook === "string") return hook;
        if (hook && typeof hook === "object") {
          return hook.text || JSON.stringify(hook);
        }
        return String(hook);
      })
      .filter(Boolean);
    return {
      name: setting.location_name || metadata.location || "Unknown",
      authority: card.authority || "unknown",
      economy: card.economy || "unknown",
      danger: card.danger || "unknown",
      hooks: normalizedHooks
    };
  }, [session, threads]);

  const submitTurn = async ({
    playerText,
    actionType,
    payload,
    label
  }) => {
    if (!sessionId) return;
    setError("");
    if (label) {
      setMessages((prev) => [...prev, { role: "player", text: label }]);
    }
    setSending(true);
    try {
      const request = { session_id: sessionId };
      if (playerText) {
        request.player_text = playerText;
      }
      if (actionType) {
        request.action_type = actionType;
      }
      if (payload && Object.keys(payload).length > 0) {
        request.payload = payload;
      }
      const response = await resolveTurn(request);
      setTurnData(response);
      if (response.narration) {
        setMessages((prev) => [
          ...prev,
          { role: "system", text: response.narration }
        ]);
      } else if (response.outcome?.narration) {
        setMessages((prev) => [
          ...prev,
          { role: "system", text: response.outcome.narration }
        ]);
      }
      if (response.needs_clarification && response.clarification_question) {
        setMessages((prev) => [
          ...prev,
          { role: "system", text: response.clarification_question }
        ]);
      } else if (response.outcome?.clarify && response.outcome?.message) {
        setMessages((prev) => [
          ...prev,
          { role: "system", text: response.outcome.message }
        ]);
      }
      if (response.outcome?.death) {
        setDeathEntry(
          response.outcome.death_journal ||
            "Your journey ends here, captured in the ship logs."
        );
        setDeathOpen(true);
      }
    } catch (err) {
      setError("Turn resolution failed. Check the API or Ollama status.");
    } finally {
      setSending(false);
    }
  };

  const handleSend = async (event) => {
    event.preventDefault();
    if (!input.trim() || !sessionId) return;
    const outgoing = input.trim();
    setInput("");
    await submitTurn({ playerText: outgoing, label: outgoing });
  };

  const handleSuggestedAction = async (action) => {
    if (!action) return;
    await submitTurn({
      playerText: "",
      actionType: action.action_type,
      payload: action.payload || {},
      label: action.label || action.action_type
    });
  };

  useEffect(() => {
    const handleKey = (event) => {
      if (
        event.key.toLowerCase() === "d" &&
        (event.ctrlKey || event.metaKey) &&
        event.shiftKey
      ) {
        event.preventDefault();
        setDevOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  const loadSidePanels = async () => {
    if (!sessionId) return;
    try {
      const [threadData, clockData] = await Promise.all([
        fetchThreads(sessionId),
        fetchClocks(sessionId)
      ]);
      setThreads(Array.isArray(threadData) ? threadData : []);
      setClocks(Array.isArray(clockData) ? clockData : []);
    } catch (err) {
      setThreads((prev) => prev);
      setClocks((prev) => prev);
    }
  };

  const handleSave = async () => {
    if (!sessionId) return;
    setError("");
    try {
      const snapshot = await exportSession(sessionId);
      const blob = new Blob([JSON.stringify(snapshot, null, 2)], {
        type: "application/json"
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `session_${sessionId}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError("Failed to export session snapshot.");
    }
  };

  const handleLoad = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const response = await importSession(payload);
      navigate(`/session/${response.session.id}`, {
        state: response
      });
    } catch (err) {
      setError("Failed to import session snapshot.");
    } finally {
      event.target.value = "";
    }
  };

  const handleRespawn = async () => {
    if (!character?.id) return;
    setError("");
    try {
      const response = await respawnCharacter(character.id);
      const refreshed = response.character || {};
      setSheetState(buildSheet(refreshed));
      setDeathOpen(false);
      setMessages((prev) => [
        ...prev,
        { role: "system", text: "Respawn successful. Continuity preserved." }
      ]);
    } catch (err) {
      setError("Respawn failed. Restart recommended.");
    }
  };

  const handleRestart = async () => {
    if (!sessionId) return;
    setError("");
    try {
      const response = await restartSession(sessionId);
      navigate(`/session/${response.session.id}`, {
        state: response
      });
    } catch (err) {
      setError("Restart failed.");
    }
  };

  useEffect(() => {
    if (!turnData?.state_diff?.character) return;
    const snapshot = turnData.state_diff.character;
    setSheetState((prev) => ({
      ...prev,
      hp: snapshot.hp ?? prev.hp,
      ap: snapshot.ap ?? prev.ap,
      statuses: snapshot.statuses ?? prev.statuses,
      resources: snapshot.resources ?? prev.resources
    }));
  }, [turnData]);

  useEffect(() => {
    loadSidePanels();
  }, [sessionId]);

  useEffect(() => {
    if (!turnData) return;
    loadSidePanels();
  }, [turnData]);
  useEffect(() => {
    if (!turnData?.rolls || turnData.rolls.length === 0) return;
    const eventBatch = turnData.rolls.map((roll, index) => ({
      id: `${Date.now()}-${index}`,
      formula: roll.formula || roll.f || "roll",
      result: roll.result ?? roll.r ?? 0
    }));
    setRollEvents(eventBatch);
    const timeout = setTimeout(() => {
      setRollEvents([]);
    }, 1600);
    return () => clearTimeout(timeout);
  }, [turnData]);

  if (!sessionId) {
    return (
      <div className="shell">
        <header className="hero">
          <h1>Session Hub</h1>
          <p>Missing session context. Create a new session first.</p>
        </header>
        <button className="btn ghost" onClick={goHome}>
          Return to Character Creation
        </button>
      </div>
    );
  }

  return (
    <div className="shell session-grid">
      <section className="panel chat-panel">
        <header className="panel-header">
          <div>
            <h2>Session #{sessionId}</h2>
            <p className="muted">Era: {era}</p>
          </div>
          <div className="header-actions">
            <button className="btn ghost" onClick={handleSave}>
              Save Snapshot
            </button>
            <label className="btn ghost file-btn">
              Load Snapshot
              <input type="file" accept="application/json" onChange={handleLoad} />
            </label>
            <button className="btn ghost" onClick={goHome}>
              New Session
            </button>
          </div>
        </header>
        <div className="chat-window">
          {messages.length === 0 ? (
            <p className="muted">Send a command to start the turn loop.</p>
          ) : (
            messages.map((message, index) => (
              <div key={index} className={`chat-bubble ${message.role}`}>
                <span>{message.text}</span>
              </div>
            ))
          )}
        </div>
        {rollEvents.length > 0 ? (
          <div className="roll-tray">
            {rollEvents.map((roll) => (
              <div key={roll.id} className="roll-chip">
                <span className="roll-formula">{roll.formula}</span>
                <span className="roll-result">{roll.result}</span>
              </div>
            ))}
          </div>
        ) : null}
        {turnData?.suggested_actions?.length ? (
          <div className="suggested-actions">
            {turnData.suggested_actions.map((action, index) => (
              <button
                key={`${action.action_type}-${index}`}
                className="btn ghost"
                type="button"
                onClick={() => handleSuggestedAction(action)}
                disabled={sending}
              >
                {action.label}
              </button>
            ))}
          </div>
        ) : null}
        <form className="chat-input" onSubmit={handleSend}>
          <input
            placeholder="Describe your action..."
            value={input}
            onChange={(event) => setInput(event.target.value)}
          />
          <button className="btn primary" disabled={sending} type="submit">
            {sending ? "Resolving" : "Send"}
          </button>
        </form>
        {error ? <p className="error">{error}</p> : null}
        <details
          className="mechanics"
          open={showMechanics}
          onToggle={(event) => setShowMechanics(event.currentTarget.open)}
        >
          <summary>Mechanics</summary>
          <div className="mechanics-body">
            <h4>Rolls</h4>
            <pre>{JSON.stringify(turnData?.rolls || [], null, 2)}</pre>
            <h4>Outcome</h4>
            <pre>{JSON.stringify(turnData?.outcome || {}, null, 2)}</pre>
            <h4>State Diff</h4>
            <pre>{JSON.stringify(turnData?.state_diff || {}, null, 2)}</pre>
          </div>
        </details>
        {devOpen ? (
          <details className="dev-panel" open>
            <summary>Dev Panel</summary>
            <div className="dev-body">
              <div>
                <h4>Session Seed</h4>
                <pre>{session?.seed ?? session?.rng_seed ?? "unknown"}</pre>
              </div>
              <div>
                <h4>Last Intent</h4>
                <pre>{JSON.stringify(turnData?.intent || {}, null, 2)}</pre>
              </div>
              <div>
                <h4>Last Mechanics</h4>
                <pre>{JSON.stringify(turnData?.outcome || {}, null, 2)}</pre>
              </div>
              <div>
                <h4>Raw LLM Output</h4>
                <pre>{turnData?.raw_llm_output || "Not available."}</pre>
              </div>
              <div>
                <h4>Parsed Intent</h4>
                <pre>{JSON.stringify(turnData?.parsed_intent || {}, null, 2)}</pre>
              </div>
              <div>
                <h4>Validation Errors</h4>
                <pre>{JSON.stringify(turnData?.validation_errors || [], null, 2)}</pre>
              </div>
            </div>
          </details>
        ) : null}
      </section>
      {deathOpen ? (
        <div className="death-modal">
          <div className="death-card">
            <h3>Death Journal</h3>
            <p>{deathEntry}</p>
            <div className="death-actions">
              <button className="btn primary" onClick={handleRestart}>
                Restart
              </button>
              <button className="btn ghost" onClick={handleRespawn}>
                Respawn
              </button>
              <label className="btn ghost file-btn">
                Load Save
                <input
                  type="file"
                  accept="application/json"
                  onChange={handleLoad}
                />
              </label>
            </div>
          </div>
        </div>
      ) : null}
      <div className="sheet-column">
        <section className="panel side-panel">
          <h3>Location Card</h3>
          <div className="state-block">
            <p className="label">Location</p>
            <p>{locationCard.name}</p>
          </div>
          <div className="state-block">
            <p className="label">Authority</p>
            <p>{locationCard.authority}</p>
          </div>
          <div className="state-block">
            <p className="label">Economy</p>
            <p>{locationCard.economy}</p>
          </div>
          <div className="state-block">
            <p className="label">Danger</p>
            <p>{locationCard.danger}</p>
          </div>
          <div className="state-block">
            <p className="label">Hooks</p>
            {locationCard.hooks?.length ? (
              <ul className="data-list">
                {locationCard.hooks.map((hook, index) => (
                  <li key={`hook-${index}`}>{hook}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">No active hooks yet.</p>
            )}
          </div>
        </section>
        <section className="panel side-panel">
          <h3>Threads</h3>
          <div className="panel-subhead">Open</div>
          {threads.filter((thread) => thread.status === "open").length === 0 ? (
            <p className="muted">No open threads.</p>
          ) : (
            <ul className="data-list">
              {threads
                .filter((thread) => thread.status === "open")
                .map((thread) => (
                  <li key={`thread-${thread.id}`}>
                    <span>{thread.text}</span>
                    <span className={`tag ${thread.urgency || "med"}`}>
                      {thread.urgency || "med"}
                    </span>
                  </li>
                ))}
            </ul>
          )}
          <div className="panel-subhead">Resolved</div>
          {threads.filter((thread) => thread.status !== "open").length === 0 ? (
            <p className="muted">No resolved threads.</p>
          ) : (
            <ul className="data-list">
              {threads
                .filter((thread) => thread.status !== "open")
                .map((thread) => (
                  <li key={`thread-${thread.id}`}>
                    <span>{thread.text}</span>
                    <span className="tag muted">{thread.status}</span>
                  </li>
                ))}
            </ul>
          )}
        </section>
        <section className="panel side-panel">
          <h3>Clocks</h3>
          {clocks.filter((clock) => clock.visibility === "player").length === 0 ? (
            <p className="muted">No visible clocks.</p>
          ) : (
            <ul className="data-list">
              {clocks
                .filter((clock) => clock.visibility === "player")
                .map((clock) => (
                  <li key={`clock-${clock.id}`}>
                    <span>{clock.name}</span>
                    <span className="tag">
                      {clock.steps_done}/{clock.steps_total}
                    </span>
                  </li>
                ))}
            </ul>
          )}
        </section>
        {devModeEnabled ? (
          <section className="panel side-panel">
            <h3>Dev Reports</h3>
            {turnData?.validation_errors?.length ? (
              <ul className="data-list">
                {turnData.validation_errors.map((errorItem, index) => (
                  <li key={`dev-error-${index}`}>{errorItem}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">No dev reports yet.</p>
            )}
            {turnData?.raw_llm_output ? (
              <details className="dev-report">
                <summary>Raw LLM Output</summary>
                <pre>{turnData.raw_llm_output}</pre>
              </details>
            ) : null}
            {turnData?.parsed_intent ? (
              <details className="dev-report">
                <summary>Parsed Intent</summary>
                <pre>{JSON.stringify(turnData.parsed_intent, null, 2)}</pre>
              </details>
            ) : null}
          </section>
        ) : null}
        <section className="panel state-panel">
          <h3>Character State</h3>
          <div className="state-block">
            <p className="label">Name</p>
            <p>{character?.name || "Unknown Operative"}</p>
          </div>
          <div className="state-block">
            <p className="label">Race</p>
            <p>{character?.race_id ? `#${character.race_id}` : "N/A"}</p>
          </div>
          <div className="state-block">
            <p className="label">Profession</p>
            <p>{character?.profession_id ? `#${character.profession_id}` : "N/A"}</p>
          </div>
          <div className="state-block">
            <p className="label">HP / AP</p>
            <p>
              {sheetState.hp ?? "?"} / {sheetState.ap ?? 0}
            </p>
          </div>
          <div className="state-block">
            <p className="label">Resources</p>
            <pre>{JSON.stringify(sheetState.resources || {}, null, 2)}</pre>
          </div>
          <div className="state-block">
            <p className="label">Last Outcome</p>
            <pre>{JSON.stringify(turnData?.outcome || {}, null, 2)}</pre>
          </div>
        </section>
        <section className="panel sheet-panel">
          <h3>Character Sheet</h3>
          <div className="sheet-section">
            <h4>Attributes</h4>
            <div className="stat-grid">
              {Object.entries(sheetState.attributes).map(([key, value]) => (
                <div key={key} className="stat-card">
                  <span className="stat-key">{key}</span>
                  <span className="stat-value">{value}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="sheet-section">
            <h4>Derived</h4>
            <div className="stat-grid">
              <div className="stat-card">
                <span className="stat-key">HP</span>
                <span className="stat-value">{sheetState.hp ?? "?"}</span>
              </div>
              <div className="stat-card">
                <span className="stat-key">AP</span>
                <span className="stat-value">{sheetState.ap ?? 0}</span>
              </div>
              <div className="stat-card">
                <span className="stat-key">AR</span>
                <span className="stat-value">{sheetState.ar ?? 0}</span>
              </div>
              <div className="stat-card">
                <span className="stat-key">Init</span>
                <span className="stat-value">{sheetState.initiative ?? 0}</span>
              </div>
              <div className="stat-card">
                <span className="stat-key">Credits</span>
                <span className="stat-value">{sheetState.credits ?? 0}</span>
              </div>
            </div>
          </div>
          <div className="sheet-section">
            <h4>Skills</h4>
            {Object.keys(sheetState.skills || {}).length === 0 ? (
              <p className="muted">No skills assigned yet.</p>
            ) : (
              <ul className="sheet-list">
                {Object.entries(sheetState.skills).map(([skill, level]) => (
                  <li key={skill}>
                    <span>{skill}</span>
                    <span className="chip">{level}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="sheet-section">
            <h4>Inventory</h4>
            {sheetState.inventory.length === 0 ? (
              <p className="muted">Inventory is empty.</p>
            ) : (
              <ul className="sheet-list">
                {sheetState.inventory.map((item, index) => (
                  <li key={`${item.base || "item"}-${index}`}>
                    <span>{item.base || item.name || "Item"}</span>
                    <span className="chip">
                      {item.quantity ? `x${item.quantity}` : "1"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="sheet-section">
            <h4>Equipped</h4>
            {Object.keys(sheetState.equipped || {}).length === 0 ? (
              <p className="muted">No items equipped.</p>
            ) : (
              <ul className="sheet-list">
                {Object.entries(sheetState.equipped).map(([slot, item]) => (
                  <li key={slot}>
                    <span>{slot}</span>
                    <span className="chip">{item}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="sheet-section">
            <h4>Statuses</h4>
            {Object.keys(sheetState.statuses || {}).length === 0 ? (
              <p className="muted">No active statuses.</p>
            ) : (
              <ul className="sheet-list">
                {Object.entries(sheetState.statuses).map(([status, data]) => (
                  <li key={status}>
                    <span>{status}</span>
                    <span className="chip">
                      L{data.level ?? 1} / D{data.duration ?? "∞"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
