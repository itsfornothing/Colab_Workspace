import { useEffect, useState } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Collaboration from '@tiptap/extension-collaboration';
import CollaborationCursor from '@tiptap/extension-collaboration-cursor';
import * as Y from 'yjs';
import { WebsocketProvider } from 'y-websocket';
import { getTokens } from '@/lib/tokenStorage';
import CollaboratorBar from './CollaboratorBar';
import {
  Bold, Italic, Strikethrough, Code, Heading1, Heading2,
  List, ListOrdered, Quote, Minus, Undo, Redo
} from 'lucide-react';
import { clsx } from 'clsx';

const WS_BASE = (import.meta.env.VITE_WS_URL || 'ws://localhost:8000').replace(/^http/, 'ws');

function ToolbarBtn({ onClick, active, title, children }) {
  return (
    <button
      onMouseDown={(e) => { e.preventDefault(); onClick(); }}
      title={title}
      className={clsx(
        'p-1.5 rounded text-sm transition-colors',
        active
          ? 'bg-primary-light text-primary'
          : 'text-[var(--color-text-hint)] hover:bg-bg-elevated hover:text-[var(--color-text-body)]'
      )}
    >
      {children}
    </button>
  );
}

export default function DocEditor({ docId, currentUser, readOnly = false }) {
  const [collaborators, setCollaborators] = useState([]);
  const [provider, setProvider] = useState(null);

  const ydoc = new Y.Doc();

  const editor = useEditor({
    editable: !readOnly,
    extensions: [
      StarterKit.configure({ history: false }),
      Placeholder.configure({ placeholder: 'Start writing…' }),
      Collaboration.configure({ document: ydoc }),
      CollaborationCursor.configure({
        provider: null, // set after provider init
        user: { name: currentUser?.full_name || 'Anonymous', color: '#6366f1' },
      }),
    ],
  });

  useEffect(() => {
    if (!docId || !editor) return;

    const { accessToken } = getTokens();
    const wsUrl = `${WS_BASE}/ws/docs/${docId}/?token=${accessToken}`;
    const wsProvider = new WebsocketProvider(wsUrl, `doc-${docId}`, ydoc);

    wsProvider.awareness.on('change', () => {
      const states = Array.from(wsProvider.awareness.getStates().values());
      setCollaborators(states.filter((s) => s.user && s.user.name !== currentUser?.full_name));
    });

    setProvider(wsProvider);

    return () => {
      wsProvider.destroy();
    };
  }, [docId]);

  if (!editor) return null;

  const e = editor;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      {!readOnly && (
        <div className="flex items-center gap-0.5 px-4 py-2 border-b border-[var(--color-border)] bg-bg-elevated flex-wrap">
          <ToolbarBtn onClick={() => e.chain().focus().toggleBold().run()} active={e.isActive('bold')} title="Bold">
            <Bold size={15} />
          </ToolbarBtn>
          <ToolbarBtn onClick={() => e.chain().focus().toggleItalic().run()} active={e.isActive('italic')} title="Italic">
            <Italic size={15} />
          </ToolbarBtn>
          <ToolbarBtn onClick={() => e.chain().focus().toggleStrike().run()} active={e.isActive('strike')} title="Strikethrough">
            <Strikethrough size={15} />
          </ToolbarBtn>
          <ToolbarBtn onClick={() => e.chain().focus().toggleCode().run()} active={e.isActive('code')} title="Inline code">
            <Code size={15} />
          </ToolbarBtn>
          <div className="w-px h-5 bg-[var(--color-border)] mx-1" />
          <ToolbarBtn onClick={() => e.chain().focus().toggleHeading({ level: 1 }).run()} active={e.isActive('heading', { level: 1 })} title="Heading 1">
            <Heading1 size={15} />
          </ToolbarBtn>
          <ToolbarBtn onClick={() => e.chain().focus().toggleHeading({ level: 2 }).run()} active={e.isActive('heading', { level: 2 })} title="Heading 2">
            <Heading2 size={15} />
          </ToolbarBtn>
          <div className="w-px h-5 bg-[var(--color-border)] mx-1" />
          <ToolbarBtn onClick={() => e.chain().focus().toggleBulletList().run()} active={e.isActive('bulletList')} title="Bullet list">
            <List size={15} />
          </ToolbarBtn>
          <ToolbarBtn onClick={() => e.chain().focus().toggleOrderedList().run()} active={e.isActive('orderedList')} title="Ordered list">
            <ListOrdered size={15} />
          </ToolbarBtn>
          <ToolbarBtn onClick={() => e.chain().focus().toggleBlockquote().run()} active={e.isActive('blockquote')} title="Quote">
            <Quote size={15} />
          </ToolbarBtn>
          <ToolbarBtn onClick={() => e.chain().focus().setHorizontalRule().run()} active={false} title="Divider">
            <Minus size={15} />
          </ToolbarBtn>
          <div className="w-px h-5 bg-[var(--color-border)] mx-1" />
          <ToolbarBtn onClick={() => e.chain().focus().undo().run()} active={false} title="Undo">
            <Undo size={15} />
          </ToolbarBtn>
          <ToolbarBtn onClick={() => e.chain().focus().redo().run()} active={false} title="Redo">
            <Redo size={15} />
          </ToolbarBtn>
          <div className="ml-auto">
            <CollaboratorBar collaborators={collaborators} />
          </div>
        </div>
      )}

      <EditorContent
        editor={editor}
        className="flex-1 overflow-y-auto px-8 py-6 prose prose-sm max-w-none focus:outline-none [&_.ProseMirror]:outline-none [&_.ProseMirror]:min-h-[400px]"
      />
    </div>
  );
}
