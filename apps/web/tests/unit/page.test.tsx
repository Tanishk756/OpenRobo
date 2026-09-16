import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import HomePage from '../../app/page';

describe('HomePage Component', () => {
  it('renders OpenRobo title and explore button', () => {
    render(<HomePage />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Global Open Robotics Commons Platform');
    expect(screen.getByTestId('explore-registry-btn')).toBeInTheDocument();
    expect(screen.getByText(/Canonical Metadata Schema/i)).toBeInTheDocument();
  });
});
