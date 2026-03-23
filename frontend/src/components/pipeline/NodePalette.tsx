import { useState } from 'react';
import type { NodeCategory } from '../../utils/pipelineTypes';
import { NODE_DEFINITIONS, CATEGORY_COLORS } from '../../utils/nodeDefinitions';

interface RegistryNode {
  type: string;
  label: string;
  category: NodeCategory;
  parameterSchema: Record<string, unknown> | null;
  registryName: string;
}

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
  'filter',
  'splitter',
  'parameter',
  'output',
];

const CATEGORY_LABELS: Record<NodeCategory, string> = {
  sensor: 'Sensors',
  slam: 'SLAM Backends',
  merger: 'Mergers',
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
        background: '#1a1a2e',
        borderRight: '1px solid #2a2a4a',
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
    background: '#2a2a4a',
    border: 'none',
    color: '#e0e0e0',
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
    background: '#0a0a14',
    border: '1px solid #2a2a4a',
    color: '#e0e0e0',
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
                    color: '#e0e0e0',
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
                        background: '#1e1e32',
                        border: `1px solid ${isHovered ? '#4a4a6a' : '#2a2a4a'}`,
                        borderRadius: 4,
                        marginBottom: 4,
                        cursor: 'grab',
                        fontSize: 11,
                        fontWeight: 600,
                        color: '#e0e0e0',
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
