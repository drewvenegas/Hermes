/**
 * Version History Page
 * 
 * Displays version history for a prompt with diff viewing and rollback capabilities.
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Container,
  Button,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  IconButton,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Paper,
  Divider,
  Tooltip,
  CircularProgress,
  Alert,
  Grid,
  Avatar,
} from '@mui/material';
import {
  History as HistoryIcon,
  Compare as CompareIcon,
  Restore as RestoreIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  Code as CodeIcon,
  ArrowBack as BackIcon,
  Check as CheckIcon,
  ChevronRight as ChevronIcon,
} from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';

// Types
interface PromptVersion {
  id: string;
  promptId: string;
  version: string;
  contentHash: string;
  content: string;
  diff: string | null;
  changeSummary: string | null;
  authorId: string;
  authorName?: string;
  createdAt: string;
  benchmarkScore?: number;
}

interface DiffChunk {
  type: 'add' | 'remove' | 'context';
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  lines: string[];
}

interface DiffResult {
  fromVersion: string;
  toVersion: string;
  diff: string;
  chunks: DiffChunk[];
}

// Diff Viewer Component
interface DiffViewerProps {
  diff: DiffResult | null;
  isLoading?: boolean;
}

function DiffViewer({ diff, isLoading }: DiffViewerProps) {
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!diff) {
    return (
      <Box sx={{ textAlign: 'center', p: 4 }}>
        <Typography color="text.secondary">
          Select two versions to compare
        </Typography>
      </Box>
    );
  }

  return (
    <Paper sx={{ overflow: 'auto', maxHeight: '60vh' }}>
      <Box sx={{ p: 2, bgcolor: 'grey.100', borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="subtitle2">
          Comparing v{diff.fromVersion} → v{diff.toVersion}
        </Typography>
      </Box>
      <Box component="pre" sx={{ m: 0, p: 2, fontFamily: 'monospace', fontSize: '0.875rem' }}>
        {diff.chunks.map((chunk, chunkIdx) => (
          <Box key={chunkIdx}>
            <Box sx={{ color: 'text.secondary', py: 0.5 }}>
              @@ -{chunk.oldStart},{chunk.oldLines} +{chunk.newStart},{chunk.newLines} @@
            </Box>
            {chunk.lines.map((line, lineIdx) => {
              const lineType = line.startsWith('+') ? 'add' : line.startsWith('-') ? 'remove' : 'context';
              const bgColor = lineType === 'add' ? 'success.light' : lineType === 'remove' ? 'error.light' : 'transparent';
              const textColor = lineType === 'add' ? 'success.dark' : lineType === 'remove' ? 'error.dark' : 'text.primary';
              
              return (
                <Box
                  key={lineIdx}
                  sx={{
                    bgcolor: bgColor,
                    color: textColor,
                    px: 1,
                    borderLeft: 3,
                    borderColor: lineType === 'add' ? 'success.main' : lineType === 'remove' ? 'error.main' : 'transparent',
                  }}
                >
                  {line}
                </Box>
              );
            })}
          </Box>
        ))}
      </Box>
    </Paper>
  );
}

// Rollback Dialog
interface RollbackDialogProps {
  open: boolean;
  version: PromptVersion | null;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}

function RollbackDialog({ open, version, onClose, onConfirm }: RollbackDialogProps) {
  const [reason, setReason] = useState('');

  const handleConfirm = () => {
    onConfirm(reason);
    setReason('');
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Rollback to Version {version?.version}</DialogTitle>
      <DialogContent>
        <Alert severity="warning" sx={{ mb: 2 }}>
          This will create a new version with the content from v{version?.version}.
        </Alert>
        <TextField
          autoFocus
          label="Rollback Reason"
          fullWidth
          multiline
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Why are you rolling back to this version?"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleConfirm} variant="contained" color="warning">
          Rollback
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// Mock data
const mockVersions: PromptVersion[] = [
  {
    id: '1',
    promptId: 'prompt-1',
    version: '3.0.0',
    contentHash: 'abc123',
    content: 'Latest content...',
    diff: null,
    changeSummary: 'Improved clarity and added examples',
    authorId: 'user-1',
    authorName: 'Alice',
    createdAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    benchmarkScore: 0.92,
  },
  {
    id: '2',
    promptId: 'prompt-1',
    version: '2.1.0',
    contentHash: 'def456',
    content: 'Previous content...',
    diff: null,
    changeSummary: 'Fixed formatting issues',
    authorId: 'user-2',
    authorName: 'Bob',
    createdAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    benchmarkScore: 0.88,
  },
  {
    id: '3',
    promptId: 'prompt-1',
    version: '2.0.0',
    contentHash: 'ghi789',
    content: 'Older content...',
    diff: null,
    changeSummary: 'Major rewrite for better performance',
    authorId: 'user-1',
    authorName: 'Alice',
    createdAt: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    benchmarkScore: 0.85,
  },
];

// Main Component
export function VersionHistory() {
  const { promptId } = useParams<{ promptId: string }>();
  const navigate = useNavigate();
  
  const [versions, setVersions] = useState<PromptVersion[]>(mockVersions);
  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);
  const [diff, setDiff] = useState<DiffResult | null>(null);
  const [isLoadingDiff, setIsLoadingDiff] = useState(false);
  const [rollbackDialog, setRollbackDialog] = useState<PromptVersion | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Toggle version selection
  const toggleVersion = (versionId: string) => {
    setSelectedVersions(prev => {
      if (prev.includes(versionId)) {
        return prev.filter(id => id !== versionId);
      }
      if (prev.length >= 2) {
        return [prev[1], versionId];
      }
      return [...prev, versionId];
    });
  };

  // Compare selected versions
  const compareVersions = async () => {
    if (selectedVersions.length !== 2) return;
    
    setIsLoadingDiff(true);
    
    // In production, fetch diff from API
    // const diff = await fetchDiff(promptId, selectedVersions[0], selectedVersions[1]);
    
    // Mock diff
    setTimeout(() => {
      setDiff({
        fromVersion: versions.find(v => v.id === selectedVersions[0])?.version || '',
        toVersion: versions.find(v => v.id === selectedVersions[1])?.version || '',
        diff: '',
        chunks: [
          {
            type: 'context',
            oldStart: 1,
            oldLines: 3,
            newStart: 1,
            newLines: 3,
            lines: [
              ' # System Prompt',
              ' ',
              ' You are a helpful assistant.',
            ],
          },
          {
            type: 'remove',
            oldStart: 4,
            oldLines: 2,
            newStart: 4,
            newLines: 0,
            lines: [
              '-Please be concise.',
              '-Avoid unnecessary details.',
            ],
          },
          {
            type: 'add',
            oldStart: 0,
            oldLines: 0,
            newStart: 4,
            newLines: 3,
            lines: [
              '+Be thorough and detailed.',
              '+Provide examples when helpful.',
              '+Ask clarifying questions if needed.',
            ],
          },
        ],
      });
      setIsLoadingDiff(false);
    }, 500);
  };

  // Handle rollback
  const handleRollback = async (reason: string) => {
    if (!rollbackDialog) return;
    
    // In production, call API
    // await rollbackToVersion(promptId, rollbackDialog.version, reason);
    
    console.log('Rolling back to', rollbackDialog.version, 'Reason:', reason);
    setRollbackDialog(null);
  };

  // Get score color
  const getScoreColor = (score?: number) => {
    if (!score) return 'default';
    if (score >= 0.9) return 'success';
    if (score >= 0.7) return 'warning';
    return 'error';
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 4 }}>
        <IconButton onClick={() => navigate(-1)}>
          <BackIcon />
        </IconButton>
        <Typography variant="h4" component="h1">
          Version History
        </Typography>
        <Chip label={`${versions.length} versions`} />
      </Box>

      <Grid container spacing={3}>
        {/* Version List */}
        <Grid item xs={12} md={5}>
          <Card>
            <CardHeader
              title="Versions"
              action={
                <Button
                  variant="contained"
                  disabled={selectedVersions.length !== 2}
                  onClick={compareVersions}
                  startIcon={<CompareIcon />}
                >
                  Compare
                </Button>
              }
            />
            <Divider />
            <List sx={{ maxHeight: '60vh', overflow: 'auto' }}>
              {versions.map((version, index) => (
                <ListItem
                  key={version.id}
                  button
                  selected={selectedVersions.includes(version.id)}
                  onClick={() => toggleVersion(version.id)}
                  sx={{
                    borderLeft: selectedVersions.includes(version.id) ? 3 : 0,
                    borderColor: 'primary.main',
                  }}
                >
                  <ListItemIcon>
                    {selectedVersions.includes(version.id) ? (
                      <Avatar sx={{ bgcolor: 'primary.main', width: 32, height: 32 }}>
                        {selectedVersions.indexOf(version.id) + 1}
                      </Avatar>
                    ) : (
                      <Avatar sx={{ bgcolor: 'grey.300', width: 32, height: 32 }}>
                        <CodeIcon fontSize="small" />
                      </Avatar>
                    )}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="subtitle1">v{version.version}</Typography>
                        {index === 0 && (
                          <Chip label="Current" size="small" color="primary" />
                        )}
                        {version.benchmarkScore && (
                          <Chip
                            label={`${(version.benchmarkScore * 100).toFixed(0)}%`}
                            size="small"
                            color={getScoreColor(version.benchmarkScore) as any}
                          />
                        )}
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          {version.changeSummary || 'No description'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {version.authorName} • {new Date(version.createdAt).toLocaleString()}
                        </Typography>
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    {index > 0 && (
                      <Tooltip title="Rollback to this version">
                        <IconButton
                          edge="end"
                          onClick={(e) => {
                            e.stopPropagation();
                            setRollbackDialog(version);
                          }}
                        >
                          <RestoreIcon />
                        </IconButton>
                      </Tooltip>
                    )}
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          </Card>
        </Grid>

        {/* Diff View */}
        <Grid item xs={12} md={7}>
          <Card>
            <CardHeader title="Diff View" />
            <Divider />
            <CardContent>
              <DiffViewer diff={diff} isLoading={isLoadingDiff} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Rollback Dialog */}
      <RollbackDialog
        open={!!rollbackDialog}
        version={rollbackDialog}
        onClose={() => setRollbackDialog(null)}
        onConfirm={handleRollback}
      />
    </Container>
  );
}

export default VersionHistory;
