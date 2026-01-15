/**
 * VersionDiff Component
 * 
 * Displays a side-by-side or unified diff between two prompt versions.
 */

import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  Chip,
  Tooltip,
} from '@mui/material';
import {
  ViewColumn as SplitIcon,
  ViewStream as UnifiedIcon,
} from '@mui/icons-material';

interface DiffLine {
  type: 'add' | 'remove' | 'context' | 'header';
  lineNumber?: { old?: number; new?: number };
  content: string;
}

interface VersionDiffProps {
  fromVersion: string;
  toVersion: string;
  lines: DiffLine[];
  mode?: 'unified' | 'split';
  onModeChange?: (mode: 'unified' | 'split') => void;
}

export function VersionDiff({
  fromVersion,
  toVersion,
  lines,
  mode = 'unified',
  onModeChange,
}: VersionDiffProps) {
  const [viewMode, setViewMode] = useState<'unified' | 'split'>(mode);

  const handleModeChange = (_: React.MouseEvent, newMode: 'unified' | 'split') => {
    if (newMode) {
      setViewMode(newMode);
      onModeChange?.(newMode);
    }
  };

  // Line colors
  const getLineStyle = (type: DiffLine['type']) => {
    switch (type) {
      case 'add':
        return { bgcolor: 'rgba(46, 160, 67, 0.15)', borderColor: 'success.main' };
      case 'remove':
        return { bgcolor: 'rgba(248, 81, 73, 0.15)', borderColor: 'error.main' };
      case 'header':
        return { bgcolor: 'rgba(88, 166, 255, 0.15)', borderColor: 'info.main' };
      default:
        return { bgcolor: 'transparent', borderColor: 'transparent' };
    }
  };

  const getLinePrefix = (type: DiffLine['type']) => {
    switch (type) {
      case 'add':
        return '+';
      case 'remove':
        return '-';
      default:
        return ' ';
    }
  };

  // Stats
  const additions = lines.filter(l => l.type === 'add').length;
  const deletions = lines.filter(l => l.type === 'remove').length;

  return (
    <Paper sx={{ overflow: 'hidden' }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          p: 2,
          bgcolor: 'grey.50',
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="subtitle2">
            v{fromVersion} → v{toVersion}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Chip
              label={`+${additions}`}
              size="small"
              color="success"
              variant="outlined"
            />
            <Chip
              label={`-${deletions}`}
              size="small"
              color="error"
              variant="outlined"
            />
          </Box>
        </Box>
        
        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={handleModeChange}
          size="small"
        >
          <ToggleButton value="unified">
            <Tooltip title="Unified View">
              <UnifiedIcon fontSize="small" />
            </Tooltip>
          </ToggleButton>
          <ToggleButton value="split">
            <Tooltip title="Split View">
              <SplitIcon fontSize="small" />
            </Tooltip>
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Diff Content */}
      {viewMode === 'unified' ? (
        <UnifiedDiffView lines={lines} getLineStyle={getLineStyle} getLinePrefix={getLinePrefix} />
      ) : (
        <SplitDiffView lines={lines} getLineStyle={getLineStyle} />
      )}
    </Paper>
  );
}

// Unified View
interface UnifiedDiffViewProps {
  lines: DiffLine[];
  getLineStyle: (type: DiffLine['type']) => { bgcolor: string; borderColor: string };
  getLinePrefix: (type: DiffLine['type']) => string;
}

function UnifiedDiffView({ lines, getLineStyle, getLinePrefix }: UnifiedDiffViewProps) {
  return (
    <Box
      component="pre"
      sx={{
        m: 0,
        p: 0,
        fontFamily: 'monospace',
        fontSize: '0.8125rem',
        lineHeight: 1.6,
        overflow: 'auto',
        maxHeight: '500px',
      }}
    >
      {lines.map((line, idx) => {
        const style = getLineStyle(line.type);
        const prefix = getLinePrefix(line.type);
        
        return (
          <Box
            key={idx}
            sx={{
              display: 'flex',
              bgcolor: style.bgcolor,
              borderLeft: 3,
              borderColor: style.borderColor,
              '&:hover': { bgcolor: 'action.hover' },
            }}
          >
            {/* Line Numbers */}
            <Box
              sx={{
                display: 'flex',
                color: 'text.secondary',
                bgcolor: 'grey.100',
                borderRight: 1,
                borderColor: 'divider',
                userSelect: 'none',
              }}
            >
              <Box sx={{ width: 50, px: 1, textAlign: 'right' }}>
                {line.lineNumber?.old || ''}
              </Box>
              <Box sx={{ width: 50, px: 1, textAlign: 'right' }}>
                {line.lineNumber?.new || ''}
              </Box>
            </Box>
            
            {/* Content */}
            <Box sx={{ flex: 1, px: 1 }}>
              <Box
                component="span"
                sx={{
                  color: line.type === 'add' ? 'success.dark' : line.type === 'remove' ? 'error.dark' : 'text.primary',
                }}
              >
                {prefix}{line.content}
              </Box>
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}

// Split View
interface SplitDiffViewProps {
  lines: DiffLine[];
  getLineStyle: (type: DiffLine['type']) => { bgcolor: string; borderColor: string };
}

function SplitDiffView({ lines, getLineStyle }: SplitDiffViewProps) {
  // Prepare left and right sides
  const leftLines: (DiffLine | null)[] = [];
  const rightLines: (DiffLine | null)[] = [];
  
  lines.forEach(line => {
    if (line.type === 'remove') {
      leftLines.push(line);
      rightLines.push(null);
    } else if (line.type === 'add') {
      leftLines.push(null);
      rightLines.push(line);
    } else {
      leftLines.push(line);
      rightLines.push(line);
    }
  });

  return (
    <Box
      sx={{
        display: 'flex',
        fontFamily: 'monospace',
        fontSize: '0.8125rem',
        lineHeight: 1.6,
        overflow: 'auto',
        maxHeight: '500px',
      }}
    >
      {/* Left Side (Old) */}
      <Box sx={{ flex: 1, borderRight: 1, borderColor: 'divider' }}>
        {leftLines.map((line, idx) => {
          const style = line ? getLineStyle(line.type) : { bgcolor: 'grey.50', borderColor: 'transparent' };
          
          return (
            <Box
              key={idx}
              sx={{
                display: 'flex',
                bgcolor: style.bgcolor,
                minHeight: 24,
              }}
            >
              <Box
                sx={{
                  width: 50,
                  px: 1,
                  textAlign: 'right',
                  color: 'text.secondary',
                  bgcolor: 'grey.100',
                  borderRight: 1,
                  borderColor: 'divider',
                }}
              >
                {line?.lineNumber?.old || ''}
              </Box>
              <Box sx={{ flex: 1, px: 1 }}>
                {line?.content || ''}
              </Box>
            </Box>
          );
        })}
      </Box>
      
      {/* Right Side (New) */}
      <Box sx={{ flex: 1 }}>
        {rightLines.map((line, idx) => {
          const style = line ? getLineStyle(line.type) : { bgcolor: 'grey.50', borderColor: 'transparent' };
          
          return (
            <Box
              key={idx}
              sx={{
                display: 'flex',
                bgcolor: style.bgcolor,
                minHeight: 24,
              }}
            >
              <Box
                sx={{
                  width: 50,
                  px: 1,
                  textAlign: 'right',
                  color: 'text.secondary',
                  bgcolor: 'grey.100',
                  borderRight: 1,
                  borderColor: 'divider',
                }}
              >
                {line?.lineNumber?.new || ''}
              </Box>
              <Box sx={{ flex: 1, px: 1 }}>
                {line?.content || ''}
              </Box>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}

export default VersionDiff;
