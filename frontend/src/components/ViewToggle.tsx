export type ViewMode = '3d' | 'pipeline';
interface ViewToggleProps { activeView: ViewMode; onViewChange: (view: ViewMode) => void; }
export function ViewToggle({ activeView, onViewChange }: ViewToggleProps) {
  return <div className="viewer-toolbar">
    <div className="viewer-heading"><h1>{activeView === '3d' ? 'Environment' : 'Pipeline studio'}</h1></div>
    <div className="view-toggle" role="group" aria-label="Workspace view">
      <button aria-pressed={activeView === '3d'} onClick={() => onViewChange('3d')}><svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m8 1 6 3.5v7L8 15l-6-3.5v-7L8 1Z M2 4.5 8 8l6-3.5M8 8v7" stroke="currentColor" strokeWidth="1.2"/></svg>3D view</button>
      <button aria-pressed={activeView === 'pipeline'} onClick={() => onViewChange('pipeline')}><svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true"><rect x="1" y="5" width="4" height="5" rx="1" stroke="currentColor"/><rect x="11" y="1" width="4" height="5" rx="1" stroke="currentColor"/><rect x="11" y="10" width="4" height="5" rx="1" stroke="currentColor"/><path d="M5 7.5h3V3.5h3M8 7.5v5h3" stroke="currentColor"/></svg>Pipeline editor</button>
    </div>
  </div>;
}
