import { useState } from 'react';
import type { NodeCategory, RegistryNode } from '../../utils/pipelineTypes';
import { NODE_DEFINITIONS, CATEGORY_COLORS } from '../../utils/nodeDefinitions';

interface NodePaletteProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  registryNodes?: RegistryNode[];
}

interface PaletteItem {
  type: string;
  label: string;
  category: NodeCategory;
  parameterSchema: Record<string, unknown> | null;
  registryName?: string;
}

const CATEGORY_ORDER: NodeCategory[] = [
  'sensor',
  'slam',
  'merger',
  'perception',  // Phase 7 DET-PIPELINE-01 (UI-SPEC Palette Layout Ordering)
  'filter',
  'splitter',
  'parameter',
  'output',
];

const CATEGORY_LABELS: Record<NodeCategory, string> = {
  sensor: 'Sensors',
  slam: 'SLAM Backends',
  merger: 'Mergers',
  perception: 'Perception',  // Phase 7 DET-PIPELINE-01
  filter: 'Filters',
  splitter: 'Splitters / Combiners',
  parameter: 'Parameters',
  output: 'Output',
};

export function NodePalette({ collapsed, onToggleCollapse, registryNodes }: NodePaletteProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);

  // Combine static definitions with registry nodes
  const allItems: PaletteItem[] = [
    ...Object.entries(NODE_DEFINITIONS).map(([key, def]) => ({
      type: key,
      label: def.label,
      category: def.category,
      parameterSchema: def.parameterSchema,
      registryName: undefined,
    })),
    ...(registryNodes ?? []).map((rn) => ({
      type: rn.type,
      label: rn.label,
      category: rn.category,
      parameterSchema: rn.parameterSchema,
      registryName: rn.registryName,
    })),
  ];

  // Filter by search query
  const query = searchQuery.toLowerCase();
  const filtered = query
    ? allItems.filter((item) => item.label.toLowerCase().includes(query))
    : allItems;

  // Group by category
  const grouped = new Map<NodeCategory, PaletteItem[]>();
  for (const item of filtered) {
    const list = grouped.get(item.category) ?? [];
    list.push(item);
    grouped.set(item.category, list);
  }

  const containerStyle: React.CSSProperties = collapsed
    ? { width: 0, overflow: 'hidden', padding: 0, position: 'relative' }
    : {
        width: 240,
        background: 'var(--surface)',
        borderRight: '1px solid var(--line)',
        height: '100%',
        overflowY: 'auto',
        padding: 8,
        position: 'relative',
        boxSizing: 'border-box',
      };

  const toggleStyle: React.CSSProperties = {
    position: 'absolute',
    right: -24,
    top: '50%',
    transform: 'translateY(-50%)',
    width: 24,
    height: 48,
    background: 'var(--line)',
    border: 'none',
    color: 'var(--ink)',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 12,
    zIndex: 10,
    borderRadius: '0 4px 4px 0',
    padding: 0,
  };

  const searchStyle: React.CSSProperties = {
    width: '100%',
    height: 28,
    background: 'var(--surface-inset)',
    border: '1px solid var(--line)',
    color: 'var(--ink)',
    fontSize: 13,
    padding: '4px 8px',
    borderRadius: 4,
    marginBottom: 8,
    boxSizing: 'border-box',
    outline: 'none',
  };

  return (
    <div style={containerStyle}>
      <button style={toggleStyle} onClick={onToggleCollapse} aria-label="Toggle node palette">
        {collapsed ? '\u25B6' : '\u25C0'}
      </button>

      {!collapsed && (
        <>
          <input
            type="text"
            placeholder="Search nodes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={searchStyle}
          />

          {CATEGORY_ORDER.map((category) => {
            const items = grouped.get(category);
            if (!items || items.length === 0) return null;

            return (
              <div key={category}>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: 'var(--ink)',
                    marginTop: 16,
                    marginBottom: 8,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: CATEGORY_COLORS[category],
                      flexShrink: 0,
                    }}
                  />
                  {CATEGORY_LABELS[category]}
                </div>

                {items.map((item) => {
                  const itemKey = `${item.type}-${item.registryName ?? ''}`;
                  const isHovered = hoveredItem === itemKey;

                  return (
                    <div
                      key={itemKey}
                      draggable="true"
                      onDragStart={(e) => {
                        e.dataTransfer.setData(
                          'application/pipeline-node',
                          JSON.stringify({
                            defKey: item.type,
                            registryName: item.registryName,
                            registrySchema: item.parameterSchema,
                          }),
                        );
                      }}
                      onMouseEnter={() => setHoveredItem(itemKey)}
                      onMouseLeave={() => setHoveredItem(null)}
                      aria-label={`${item.label} (${CATEGORY_LABELS[item.category]})`}
                      style={{
                        padding: 8,
                        background: 'var(--surface-raised)',
                        border: `1px solid ${isHovered ? 'var(--line-strong)' : 'var(--line)'}`,
                        borderRadius: 4,
                        marginBottom: 4,
                        cursor: 'grab',
                        fontSize: 11,
                        fontWeight: 600,
                        color: 'var(--ink)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                      }}
                    >
                      <div
                        style={{
                          width: 3,
                          height: 20,
                          borderRadius: 2,
                          background: CATEGORY_COLORS[item.category],
                          flexShrink: 0,
                        }}
                      />
                      {item.label}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
