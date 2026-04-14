import { useState, useRef, useEffect, useCallback } from 'react';
import { useDetectorStore, type LifterBackend } from '../stores/detectorStore';
import { CapabilityBadge } from './CapabilityBadge';

// D-05-analogous for lifters: option rows show license + outputs_oriented
// (license = text pill e.g. "MIT"; outputs_oriented = boolean — true for PCA-OBB/Phase 4,
// false for MedianDepth. CapabilityBadge D-04 rules handle both types.)
const LIFTER_BADGE_KEYS: Array<keyof LifterBackend['capabilities']> = [
  'license',
  'outputs_oriented',
];

export function LifterDropdown({ onSelect }: { onSelect: (name: string) => void }) {
  const lifters = useDetectorStore((s) => s.lifters);
  const activeLifter = useDetectorStore((s) => s.activeLifter);
  const activeLifterDisplay = useDetectorStore((s) => s.activeLifterDisplay);

  const [isOpen, setIsOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Click-outside handler
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  // Escape key handler
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [isOpen]);

  const handleItemClick = useCallback(
    (lifterName: string) => {
      if (lifterName !== activeLifter) {
        onSelect(lifterName);
      }
      setIsOpen(false);
    },
    [activeLifter, onSelect],
  );

  const triggerStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    background: '#12122a',
    border: `1px solid ${hovered ? '#2ecc71' : '#444'}`,
    borderRadius: isOpen ? '4px 4px 0 0' : '4px',
    padding: '8px 16px',
    cursor: 'pointer',
  };

  const listStyle: React.CSSProperties = {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: 0,
    background: '#12122a',
    border: '1px solid #2a2a4a',
    borderRadius: '0 0 4px 4px',
    zIndex: 100,
    maxHeight: '240px',
    overflowY: 'auto',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)',
  };

  return (
    <div ref={wrapperRef} style={{ position: 'relative' }}>
      <div
        style={triggerStyle}
        onClick={() => setIsOpen(!isOpen)}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <span style={{ fontSize: '13px', fontWeight: 400, color: lifters.length === 0 ? '#888' : '#e0e0e0' }}>
          {lifters.length === 0 ? 'Loading lifters...' : activeLifterDisplay}
        </span>
        {lifters.length > 0 && (
          <span style={{ fontSize: '10px', color: '#888' }}>{'\u25BC'}</span>
        )}
      </div>

      {isOpen && (
        <div style={listStyle}>
          {lifters.length === 0 ? (
            <div style={{ padding: '8px 16px', fontSize: '11px', color: '#666' }}>
              No lifters available
            </div>
          ) : (
            lifters.map((lifter) => {
              const isActive = lifter.name === activeLifter;
              const isAvailable = lifter.available;

              const itemStyle: React.CSSProperties = {
                padding: '8px 16px',
                cursor: isAvailable ? 'pointer' : 'not-allowed',
                borderLeft: isActive ? '2px solid #2ecc71' : '2px solid transparent',
                background: isActive ? 'rgba(46, 204, 113, 0.08)' : 'transparent',
                opacity: isAvailable ? 1 : 0.4,
              };

              return (
                <div
                  key={lifter.name}
                  style={itemStyle}
                  title={!isAvailable ? (lifter.reason ?? 'Unavailable') : undefined}
                  onClick={() => {
                    if (isAvailable) handleItemClick(lifter.name);
                  }}
                  onMouseEnter={(e) => {
                    if (isAvailable && !isActive) {
                      e.currentTarget.style.background = '#222244';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (isAvailable) {
                      e.currentTarget.style.background = isActive
                        ? 'rgba(46, 204, 113, 0.08)'
                        : 'transparent';
                    }
                  }}
                >
                  <div style={{ fontSize: '13px', fontWeight: 400, color: isAvailable ? '#e0e0e0' : '#555' }}>
                    {lifter.display}
                  </div>
                  <div style={{ marginTop: '4px', display: 'flex', flexWrap: 'wrap' }}>
                    {LIFTER_BADGE_KEYS.map((key) => (
                      <CapabilityBadge
                        key={key}
                        label={key}
                        value={lifter.capabilities[key]}
                      />
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
