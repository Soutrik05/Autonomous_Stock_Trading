-- Migration 0012: Add initial_stop_paise and peak_price_paise to positions for graduated trailing stop mechanics
ALTER TABLE positions ADD COLUMN initial_stop_paise INTEGER;
ALTER TABLE positions ADD COLUMN peak_price_paise INTEGER;

