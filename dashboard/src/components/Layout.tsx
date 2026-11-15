import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Header from './Header';
import Footer from './Footer';

export default function Layout() {
  // The header is `position: fixed` (so it can frost/hide on scroll), so it no longer
  // reserves its own space in the document flow -- this pads <main> to match its
  // current rendered height instead, so content never starts out hidden underneath it.
  const [headerHeight, setHeaderHeight] = useState(0);

  return (
    <div className="flex flex-col min-h-screen relative overflow-x-hidden">
      {/* Application Content Layer */}
      <div className="relative z-10 flex flex-col min-h-screen">
        <Header onHeightChange={setHeaderHeight} />
        <main className="flex-grow" style={{ paddingTop: headerHeight }}>
          <Outlet />
        </main>
        <Footer />
      </div>
    </div>
  );
}
