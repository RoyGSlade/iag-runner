import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createCharacter,
  createSession,
  fetchEras,
  fetchProfessions,
  fetchRaces,
  fetchTrainings
} from "../api/client";

const defaultForm = {
  era: "",
  customEra: "",
  settingType: "space station",
  toneTags: "",
  inspirationsText: "",
  locationName: "",
  race: "",
  profession: "",
  training: "",
  level: 1,
  advanced: false
};

export default function CharacterCreation() {
  const [form, setForm] = useState(defaultForm);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [options, setOptions] = useState({
    eras: [],
    races: [],
    trainings: [],
    professions: []
  });
  const navigate = useNavigate();

  useEffect(() => {
    let active = true;
    const loadOptions = async () => {
      try {
        const [eras, races, trainings, professions] = await Promise.all([
          fetchEras(),
          fetchRaces(),
          fetchTrainings(),
          fetchProfessions()
        ]);
        if (!active) return;
        setOptions({
          eras,
          races,
          trainings,
          professions
        });
        setForm((prev) => ({
          ...prev,
          era: prev.era || (eras[0]?.name ?? "Space"),
          race: prev.race || races[0]?.name || "",
          training: prev.training || trainings[0]?.name || "",
          profession: prev.profession || professions[0]?.name || "Bounty Hunter"
        }));
      } catch (err) {
        setError("Failed to load selection lists.");
      }
    };
    loadOptions();
    return () => {
      active = false;
    };
  }, []);

  const updateField = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const toggleAdvanced = () => {
    setForm((prev) => ({ ...prev, advanced: !prev.advanced }));
  };

  const selectedEra = useMemo(() => {
    if (!Array.isArray(options.eras)) return null;
    return options.eras.find((era) => era.name === form.era) || null;
  }, [options.eras, form.era]);

  const selectedRace = useMemo(() => {
    if (!Array.isArray(options.races)) return null;
    return options.races.find((race) => race.name === form.race) || null;
  }, [options.races, form.race]);

  const selectedTraining = useMemo(() => {
    if (!Array.isArray(options.trainings)) return null;
    return (
      options.trainings.find((training) => training.name === form.training) || null
    );
  }, [options.trainings, form.training]);

  const selectedProfession = useMemo(() => {
    if (!Array.isArray(options.professions)) return null;
    return (
      options.professions.find(
        (profession) => profession.name === form.profession
      ) || null
    );
  }, [options.professions, form.profession]);

  const handleCreate = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const eraName = form.advanced && form.customEra ? form.customEra : form.era;
      const toneTags = form.toneTags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean);
      const settingType = form.settingType || "space station";
      const session = await createSession({
        era: eraName || "Space",
        setting: {
          type: settingType,
          tone_tags: toneTags,
          inspirations_text: form.inspirationsText.trim(),
          location_name: form.locationName.trim() || null
        }
      });
      const character = await createCharacter({
        session_id: session.id,
        race: form.race || "Android",
        profession: form.profession || "Bounty Hunter",
        training: form.training || null,
        level: form.advanced ? Number(form.level) || 1 : 1
      });
      navigate(`/session/${session.id}`, {
        state: { session, character }
      });
    } catch (err) {
      setError("Failed to create session or character. Check API.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="shell">
      <header className="hero">
        <span className="eyebrow">Infinite Ages Genesis Runner</span>
        <h1>Character Creation</h1>
        <p>Forge a new operative and drop into the session hub.</p>
      </header>
      <form className="panel form-grid" onSubmit={handleCreate}>
        <div className="field">
          <label>Era</label>
          <select name="era" value={form.era} onChange={updateField}>
            {options.eras.map((era) => (
              <option key={era.id} value={era.name}>
                {era.name}
              </option>
            ))}
          </select>
          {selectedEra ? (
            <div className="preview">
              <p>{selectedEra.description || "No era description yet."}</p>
              <div className="chip-row">
                {(selectedEra.tags || []).map((tag) => (
                  <span key={tag} className="chip">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>
        <div className="field">
          <label>Setting Type</label>
          <select
            name="settingType"
            value={form.settingType}
            onChange={updateField}
          >
            <option value="frontier town">Frontier town</option>
            <option value="megacity">Megacity</option>
            <option value="mining outpost">Mining outpost</option>
            <option value="moonbase">Moonbase</option>
            <option value="jungle ruin">Jungle ruin</option>
            <option value="desert highway">Desert highway</option>
            <option value="floating arcology">Floating arcology</option>
            <option value="undersea habitat">Undersea habitat</option>
            <option value="space station">Space station</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div className="field">
          <label>Tone tags</label>
          <input
            name="toneTags"
            value={form.toneTags}
            onChange={updateField}
            placeholder="noir, mystery, high-stakes"
          />
        </div>
        <div className="field">
          <label>Inspirations</label>
          <input
            name="inspirationsText"
            value={form.inspirationsText}
            onChange={updateField}
            placeholder="Blade Runner, England, Clint Eastwood"
          />
        </div>
        <div className="field">
          <label>Location Name (optional)</label>
          <input
            name="locationName"
            value={form.locationName}
            onChange={updateField}
            placeholder="Leave blank to auto-generate"
          />
        </div>
        <div className="field">
          <label>Race</label>
          <select name="race" value={form.race} onChange={updateField}>
            {options.races.map((race) => (
              <option key={race.id} value={race.name}>
                {race.name}
              </option>
            ))}
          </select>
          {selectedRace ? (
            <div className="preview">
              <p>{selectedRace.short_desc || "No race description yet."}</p>
              {selectedRace.attribute_bonus ? (
                <pre>
                  {JSON.stringify(selectedRace.attribute_bonus, null, 2)}
                </pre>
              ) : null}
              <div className="chip-row">
                {(selectedRace.traits || []).map((trait) => (
                  <span key={trait} className="chip">
                    {trait}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>
        <div className="field">
          <label>Profession</label>
          <select
            name="profession"
            value={form.profession}
            onChange={updateField}
          >
            {options.professions.map((profession) => (
              <option key={profession.id} value={profession.name}>
                {profession.name}
              </option>
            ))}
          </select>
          {selectedProfession ? (
            <div className="preview">
              <p>{selectedProfession.short_desc || "No details yet."}</p>
              {selectedProfession.starting_credits != null ? (
                <p className="muted">
                  Starting credits: {selectedProfession.starting_credits}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="field">
          <label>Training</label>
          <select
            name="training"
            value={form.training}
            onChange={updateField}
          >
            <option value="">None</option>
            {options.trainings.map((training) => (
              <option key={training.id} value={training.name}>
                {training.name}
              </option>
            ))}
          </select>
          {selectedTraining ? (
            <div className="preview">
              <p>{selectedTraining.short_desc || "No training details yet."}</p>
              {selectedTraining.bonuses ? (
                <pre>{JSON.stringify(selectedTraining.bonuses, null, 2)}</pre>
              ) : null}
              {selectedTraining.majors ? (
                <ul className="preview-list">
                  {selectedTraining.majors.map((major) => (
                    <li key={major.name || major.skill}>
                      {major.name || major.skill}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </div>
        <button className="btn primary" disabled={loading} type="submit">
          {loading ? "Initializing..." : "Create Session + Character"}
        </button>
        <button
          type="button"
          className="btn ghost"
          onClick={toggleAdvanced}
        >
          {form.advanced ? "Hide Advanced" : "Show Advanced"}
        </button>
        {form.advanced ? (
          <div className="advanced-grid">
            <div className="field">
              <label>Custom Era</label>
              <input
                name="customEra"
                value={form.customEra}
                onChange={updateField}
                placeholder="Optional"
              />
            </div>
            <div className="field">
              <label>Level</label>
              <input
                type="number"
                min="1"
                name="level"
                value={form.level}
                onChange={updateField}
              />
            </div>
          </div>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
      </form>
    </div>
  );
}
