import { useState, useEffect, useRef } from 'react';
import { usePipelineStore } from '../../stores/pipelineStore';
import { deserializeGraph } from '../../utils/pipelineSerializer';
import { NODE_DEFINITIONS } from '../../utils/nodeDefinitions';
import { ConfirmModal } from '../ConfirmModal';
import type { PipelineNode, PipelineEdge } from '../../utils/pipelineTypes';

export function PresetSelector() {
  const activePreset = usePipelineStore((s) => s.activePreset);
  const availablePresets = usePipelineStore((s) => s.availablePresets);
  const isDirty = usePipelineStore((s) => s.isDirty);

  const [showDropdown, setShowDropdown] = useState(false);
  const [showSaveInput, setShowSaveInput] = useState(false);
  const [saveInputName, setSaveInputName] = useState('');
  const [showConfirm, setShowConfirm] = useState(false);
  const [pendingPresetName, setPendingPresetName] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch presets on mount
  useEffect(() => {
    fetch('/api/pipeline/presets')
      .then((res) => res.json())
      .then((data) => {
        if (data.presets) {
          usePipelineStore.getState().setAvailablePresets(data.presets);
        }
      })
      .catch(() => {
        // Presets endpoint may not be available yet
      });
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
        setShowSaveInput(false);
      }
    }
    if (showDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showDropdown]);

  function handleLoadPreset(name: string) {
    if (isDirty) {
      setPendingPresetName(name);
      setShowConfirm(true);
      setShowDropdown(false);
      return;
    }
    doLoadPreset(name);
  }

  function doLoadPreset(name: string) {
    setShowConfirm(false);
    setShowDropdown(false);

    fetch(`/api/pipeline/presets/${encodeURIComponent(name)}`)
      .then((res) => res.json())
      .then((data) => {
        const { nodes, edges } = deserializeGraph(
          { nodes: data.nodes, edges: data.edges },
          NODE_DEFINITIONS,
        );
        usePipelineStore
          .getState()
          .loadPresetGraph(nodes as PipelineNode[], edges as PipelineEdge[], name);
      })
      .catch(() => {
        // Failed to load preset
      });
  }

  function handleSavePreset() {
    if (!saveInputName.trim()) return;
    const config = usePipelineStore.getState().serializeForApply();

    fetch('/api/pipeline/presets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: saveInputName.trim(),
        nodes: config.nodes,
        edges: config.edges,
      }),
    })
      .then(() => {
        // Refresh presets
        return fetch('/api/pipeline/presets');
      })
      .then((res) => res.json())
      .then((data) => {
        if (data.presets) {
          usePipelineStore.getState().setAvailablePresets(data.presets);
        }
      })
      .catch(() => {
        // Save failed
      });

    setSaveInputName('');
    setShowSaveInput(false);
    setShowDropdown(false);
  }

  const dropdownButtonStyle: React.CSSProperties = {
    background: '#1e1e32',
    border: '1px solid #2a2a4a',
    color: '#e0e0e0',
    padding: '4px 12px',
    borderRadius: 4,
    fontSize: 13,
    cursor: 'pointer',
  };

  const dropdownMenuStyle: React.CSSProperties = {
    position: 'absolute',
    bottom: '100%',
    left: 0,
    background: '#1e1e32',
    border: '1px solid #2a2a4a',
    borderRadius: 4,
    zIndex: 100,
    minWidth: 200,
    maxHeight: 300,
    overflowY: 'auto',
    marginBottom: 4,
  };

  const presetItemStyle: React.CSSProperties = {
    padding: 8,
    cursor: 'pointer',
    fontSize: 13,
    color: '#e0e0e0',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  };

  return (
    <div
      ref={dropdownRef}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 8, position: 'relative' }}
    >
      <span style={{ fontSize: 11, fontWeight: 600, color: '#aaa' }}>Preset:</span>
      <button style={dropdownButtonStyle} onClick={() => setShowDropdown(!showDropdown)}>
        {activePreset ?? 'Custom'}
      </button>

      {showDropdown && (
        <div style={dropdownMenuStyle}>
          {availablePresets.map((preset) => (
            <div
              key={preset.name}
              style={presetItemStyle}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.background = '#242448';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = 'transparent';
              }}
              onClick={() => handleLoadPreset(preset.name)}
            >
              <span>{preset.name}</span>
              {preset.builtIn && (
                <span style={{ fontSize: 10, color: '#888', fontStyle: 'italic' }}>Built-in</span>
              )}
            </div>
          ))}

          {/* Separator */}
          <div style={{ borderTop: '1px solid #2a2a4a', margin: '4px 0' }} />

          {/* Save option */}
          {!showSaveInput ? (
            <div
              style={{ ...presetItemStyle, color: '#4fc3f7' }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.background = '#242448';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = 'transparent';
              }}
              onClick={() => setShowSaveInput(true)}
            >
              Save Current...
            </div>
          ) : (
            <div style={{ padding: 8, display: 'flex', gap: 4 }}>
              <input
                type="text"
                placeholder="Preset name"
                value={saveInputName}
                onChange={(e) => setSaveInputName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSavePreset();
                }}
                style={{
                  flex: 1,
                  background: '#0a0a14',
                  border: '1px solid #2a2a4a',
                  color: '#e0e0e0',
                  fontSize: 11,
                  padding: '4px 8px',
                  borderRadius: 3,
                  outline: 'none',
                }}
                autoFocus
              />
              <button
                onClick={handleSavePreset}
                style={{
                  background: '#4fc3f7',
                  color: '#0a0a14',
                  border: 'none',
                  borderRadius: 3,
                  fontSize: 11,
                  fontWeight: 600,
                  padding: '4px 8px',
                  cursor: 'pointer',
                }}
              >
                Save
              </button>
            </div>
          )}
        </div>
      )}

      {showConfirm && (
        <ConfirmModal
          heading="Load Preset"
          body={`You have unsaved changes. Load preset '${pendingPresetName}' and discard current graph?`}
          confirmLabel="Load"
          cancelLabel="Cancel"
          onConfirm={() => doLoadPreset(pendingPresetName)}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  );
}
