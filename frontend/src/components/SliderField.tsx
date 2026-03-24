import { useState, useRef, useEffect } from 'react';
import './SliderField.css';

interface SliderFieldProps {
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
  label?: string;
  isInteger?: boolean;
  disabled?: boolean;
  showInput?: boolean;
  sigFigs?: number;
  className?: string;
}

/** Format a number to N significant figures, preserving integers. */
function formatSigFigs(val: number, sigFigs: number, isInteger: boolean): string {
  if (isInteger) return String(Math.round(val));
  if (val === 0) return '0.' + '0'.repeat(sigFigs - 1);
  return Number(val.toPrecision(sigFigs)).toString();
}

export default function SliderField({
  min,
  max,
  step,
  value,
  onChange,
  label,
  isInteger = false,
  disabled = false,
  showInput = true,
  sigFigs = 3,
  className,
}: SliderFieldProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // When user starts editing, populate draft with current value
  const handleFocus = () => {
    setDraft(formatSigFigs(value, sigFigs, isInteger));
    setEditing(true);
  };

  // On blur, commit the draft value
  const handleBlur = () => {
    setEditing(false);
    const parsed = parseFloat(draft);
    if (isNaN(parsed)) return;
    let clamped = Math.min(Math.max(parsed, min), max);
    if (isInteger) clamped = Math.round(clamped);
    onChange(clamped);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') inputRef.current?.blur();
    if (e.key === 'Escape') {
      setDraft(formatSigFigs(value, sigFigs, isInteger));
      inputRef.current?.blur();
    }
  };

  const handleRangeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let val = parseFloat(e.target.value);
    if (isInteger) val = Math.round(val);
    onChange(val);
  };

  // Keep draft in sync when value changes externally while not editing
  useEffect(() => {
    if (!editing) setDraft(formatSigFigs(value, sigFigs, isInteger));
  }, [value, sigFigs, isInteger, editing]);

  const displayValue = editing ? draft : formatSigFigs(value, sigFigs, isInteger);

  return (
    <div className={`slider-field${className ? ` ${className}` : ''}`}>
      {label && <span className="slider-field__label">{label}</span>}
      <input
        className="slider-field__range"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={handleRangeChange}
        disabled={disabled}
      />
      {showInput && (
        <input
          ref={inputRef}
          className="slider-field__number"
          type="text"
          inputMode="decimal"
          value={displayValue}
          onChange={(e) => setDraft(e.target.value)}
          onFocus={handleFocus}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
      )}
    </div>
  );
}
