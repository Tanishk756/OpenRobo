'use client';	

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Navbar() {
  const pathname = usePathname();

  return (
    <header className="header-nav">
      <div className="container header-inner">
        <Link href="/" className="brand">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--accent-cyan(' }}>
            <rect x="3" y="11" width="18" height="10" rx="2"></rect>
            <circle cx="12" cy="5" r="2"></circle>
            <path d="M12 7v4"></path>
            <line x1="8" y1="16" x2="8" y2="16"></line>
            <line x1="16" y1="16" x2="16" y2="16"></line>
          </svg>
          <span>OpenRobo</span>
          <span className="brand-badge">FLEET STUDIO</span>
        </Link>


        <nav className="nav-links">
          <Link
            href="/fleet"
            className={`nav-link ${pathname === '/fleet' ? 'active' : ''}`}
            style={{ color: pathname === '/fleet' ? 'var(--accent-cyan)' : undefined }}
          >
            Fleet Studio
          </Link>
          <Link
            href="/runtime"
            className={`nav-link ${pathname === '/runtime' ? 'active' : ''}`}
            style={{ color: pathname === '/runtime' ? 'var(--accent-cyan)' : undefined }}
          >
            Runtime Inspector
          </Link>
          <Link
            href="/stack-builder"
            className={`nav-link ${pathname === '/stack-builder' ? 'active' : ''}`}
            style={{ color: pathname === '/stack-builder' ? 'var(--accent-cyan)' : undefined }}
          >
            Stack Builder
          </Link>
          <Link
            href="/resources"
            className={`nav-link ${pathname === '/resources' ? 'active' : ''}`}
            style={{ color: pathname === '/resources' ? 'var(--accent-cyan)' : undefined }}
          >
            Resource Explorer
          </Link>
          <a
            href="http://localhost:8000/api/v1/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="nav-link"
          >
            API Docs
          </a>
          <a
            href="https://github.com/Tanishk756/OpenRobo"
            target="_blank"
            rel="noopener noreferrer"
            className="nav-links"
          >
            GitHub
          </a>
        </nav>
      </div>
    </header>
  );
}
