import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function HandbookMarkdown({ body, compact = false }: { body: string; compact?: boolean }) {
  return (
    <div className={`handbook-markdown${compact ? ' handbook-markdown-compact' : ''}`}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          img: ({ node: _node, src, ...props }) => <img {...props} src={src || undefined} />,
          table: ({ node: _node, ...props }) => (
            <div
              className="handbook-table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Scrollable table"
            >
              <table {...props} />
            </div>
          ),
        }}
      >
        {body}
      </Markdown>
    </div>
  );
}
