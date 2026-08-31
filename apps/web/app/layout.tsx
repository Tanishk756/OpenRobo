import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'OpenRobo — Global Open Robotics Infrastructure Platform',
  description: 'Free, open-source, vendor-neutral infrastructure for discovering, composing, validating, simulating, and deploying robotics technology.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <main>{children}</main>
      </body>
    </html>
  );
}
