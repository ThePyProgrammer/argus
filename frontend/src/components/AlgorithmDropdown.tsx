import { useState, useRef, useEffect, useCallback } from 'react';
import { useSlamStore } from '../stores/slamStore';
import { CapabilityBadge } from './CapabilityBadge';

export function AlgorithmDropdown({ onSelect }: { onSelect: (name: string) => void }) {
  const backends = useSlamStore((s) => s.backends);
  const activeBackend = useSlamStore((s) => s.activeBackend);
  const activeDisplay = useSlamStore((s) => s.activeDisplay);

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
    (backendName: string) => {
      if (backendName !== activeBackend) {
        onSelect(backendName);
      }
      setIsOpen(false);
    },
    [activeBackend, onSelect],
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
        <span style={{ fontSize: '13px', fontWeight: 400, color: backends.length === 0 ? '#888' : '#e0e0e0' }}>
          {backends.length === 0 ? 'Loading backends...' : activeDisplay}
        </span>
        {backends.length > 0 && (
          <span style={{ fontSize: '10px', color: '#888' }}>{'\u25BC'}</span>
        )}
      </div>

      {isOpen && (
        <div style={listStyle}>
          {backends.length === 0 ? (
            <div style={{ padding: '8px 16px', fontSize: '11px', color: '#666' }}>
              No backends available
            </div>
          ) : (
            backends.map((backend) => {
              const isActive = backend.name === activeBackend;
              const isAvailable = backend.available;

              const itemStyle: React.CSSProperties = {
                padding: '8px 16px',
                cursor: isAvailable ? 'pointer' : 'not-allowed',
                borderLeft: isActive ? '2px solid #2ecc71' : '2px solid transparent',
                background: isActive ? 'rgba(46, 204, 113, 0.08)' : 'transparent',
                opacity: isAvailable ? 1 : 0.4,
              };

              const capabilities = Object.entries(backend.capabilities)
                .filter(([, v]) => v === true)
                .map(([k]) => k);

              return (
                <div
                  key={backend.name}
                  style={itemStyle}
                  title={!isAvailable ? (backend.reason ?? 'Unavailable') : undefined}
                  onClick={() => {
                    if (isAvailable) handleItemClick(backend.name);
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
                    {backend.display}
                  </div>
                  {capabilities.length > 0 && (
                    <div style={{ marginTop: '4px', display: 'flex', flexWrap: 'wrap' }}>
                      {capabilities.map((cap) => (
                        <CapabilityBadge key={cap} name={cap} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
