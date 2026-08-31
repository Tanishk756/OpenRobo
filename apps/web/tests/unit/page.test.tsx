import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import HomePage from '../../app/page';

describe('HomePage Foundation Component', () => {
  it('renders OpenRobo title and foundation status', () => {
    render(<HomePage />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('OpenRobo');
    expect(screen.getByText(/Global Open Robotics Commons Platform/i)).toBeInTheDocument();
    expect(screen.getByText(/Platform Foundation Status/i)).toBeInTheDocument();
  });
});
