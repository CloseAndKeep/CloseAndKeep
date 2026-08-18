"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export type NoteTemplate = {
  id: number;
  name: string;
  body: string;
  created_at: string;
};

const MAX_TEMPLATES = 20;

type NoteTemplatesProps = {
  note: string;
  onApply: (body: string) => void;
};

export function NoteTemplates({ note, onApply }: NoteTemplatesProps) {
  const [templates, setTemplates] = useState<NoteTemplate[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [saving, setSaving] = useState(false);
  const [showSave, setShowSave] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await apiFetch<NoteTemplate[]>("/note-templates", {
          errorMessage: "Unable to load saved notes.",
        });
        if (active) setTemplates(data);
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load saved notes.");
        }
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);

  function apply(id: string) {
    setSelectedId(id);
    const template = templates.find((item) => String(item.id) === id);
    if (template) onApply(template.body);
  }

  async function saveCurrent() {
    const name = saveName.trim();
    const body = note.trim();
    if (!name || !body) return;
    setSaving(true);
    setError(null);
    setStatus(null);
    try {
      const created = await apiFetch<NoteTemplate>("/note-templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, body }),
        errorMessage: "Unable to save note template.",
      });
      setTemplates((prev) => [created, ...prev]);
      setSaveName("");
      setShowSave(false);
      setStatus("Saved note template.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save note template.");
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    setError(null);
    setStatus(null);
    try {
      await apiFetch(`/note-templates/${id}`, {
        method: "DELETE",
        errorMessage: "Unable to delete note template.",
      });
      setTemplates((prev) => prev.filter((item) => item.id !== id));
      if (selectedId === String(id)) setSelectedId("");
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Unable to delete note template.");
    }
  }

  const atCap = templates.length >= MAX_TEMPLATES;
  const canSave = Boolean(note.trim()) && !atCap;

  return (
    <div className="mt-2 space-y-2">
      {templates.length > 0 ? (
        <div>
          <label className="block text-sm font-medium text-espresso" htmlFor="saved-note-template">
            Use a saved note
          </label>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <select
              id="saved-note-template"
              className="field-input min-w-[12rem] flex-1"
              value={selectedId}
              onChange={(event) => apply(event.target.value)}
            >
              <option value="">Choose a template…</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
            {selectedId ? (
              <button
                type="button"
                className="text-xs text-stone-500 hover:text-rose-700"
                onClick={() => void remove(Number(selectedId))}
              >
                Delete
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {!showSave ? (
        <button
          type="button"
          className="text-sm text-wood-dark underline-offset-2 hover:underline disabled:text-stone-400 disabled:no-underline"
          disabled={!canSave}
          onClick={() => {
            setShowSave(true);
            setStatus(null);
            setError(null);
          }}
        >
          {atCap ? "Saved-note limit reached (20)" : "Save current note as template"}
        </button>
      ) : (
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[10rem] flex-1">
            <label className="block text-xs font-medium text-espresso" htmlFor="new-template-name">
              Template name
            </label>
            <input
              id="new-template-name"
              className="mt-1 field-input"
              value={saveName}
              onChange={(event) => setSaveName(event.target.value)}
              placeholder="After demo"
              maxLength={120}
            />
          </div>
          <button
            type="button"
            className="rounded-xl bg-wood px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
            disabled={saving || !saveName.trim() || !note.trim()}
            onClick={() => void saveCurrent()}
          >
            {saving ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            className="text-sm text-stone-600 hover:text-espresso"
            onClick={() => {
              setShowSave(false);
              setSaveName("");
            }}
          >
            Cancel
          </button>
        </div>
      )}

      {error ? <p className="text-xs text-rose-700">{error}</p> : null}
      {status ? <p className="text-xs text-emerald-800">{status}</p> : null}
    </div>
  );
}
