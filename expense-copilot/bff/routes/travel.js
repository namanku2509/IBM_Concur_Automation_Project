/**
 * Travel booking workflow — flights + hotels.
 *
 * Every confirmed booking is recorded as a real Layer 3 corporate-card
 * transaction so it appears in the employee's "available transactions" list
 * and can be matched against a receipt in the expense report flow.
 *
 * Flights:
 *   POST /flights/search         — search by from/to/date → return matching flights
 *   GET  /flights/:id/seats      — return seat map for a flight
 *   POST /bookings               — confirm a flight booking → creates card txn
 *
 * Hotels:
 *   POST /hotels/search          — search by city/checkin/checkout → return hotels
 *   POST /hotel-bookings         — confirm a hotel booking → creates card txn
 *
 * Claims:
 *   POST /claims                 — create an expense report from confirmed bookings
 *
 * State:
 *   GET  /state                  — current bookings + claims for an employee
 */
const express  = require('express');
const { v4: uuidv4 } = require('uuid');
const layer3   = require('../services/layer3Service');

const router = express.Router();
const DEFAULT_EMPLOYEE_ID = 'EMP001';

// In-memory stores (sufficient for demo; swap for DB in production)
const bookings      = new Map();
const hotelBookings = new Map();
const claims        = new Map();

// ─────────────────────────────────────────────────────────────────────────────
// Flight inventory
// Each entry contains flights for a specific route.  The search returns all
// flights whose from/to match the requested route (case-insensitive).
// ─────────────────────────────────────────────────────────────────────────────
const FLIGHTS = [
  // DEL ↔ BOM
  { id: 'AI-101',  airline: 'Air India',          number: 'AI 101',  from: 'DEL', to: 'BOM', depart: '06:00', arrive: '08:10', duration: '2h 10m', cabin: 'Economy',      price: 5850,  stops: 0, badge: 'Early bird',    aircraft: 'A320' },
  { id: 'AI-302',  airline: 'Air India',          number: 'AI 302',  from: 'DEL', to: 'BOM', depart: '07:10', arrive: '09:20', duration: '2h 10m', cabin: 'Economy Flex', price: 6840,  stops: 0, badge: 'Recommended',   aircraft: 'A321' },
  { id: '6E-5104', airline: 'IndiGo',             number: '6E 5104', from: 'DEL', to: 'BOM', depart: '09:25', arrive: '11:35', duration: '2h 10m', cabin: 'Economy',      price: 6120,  stops: 0, badge: 'Best value',    aircraft: 'A320neo' },
  { id: 'UK-955',  airline: 'Air India Express',  number: 'IX 955',  from: 'DEL', to: 'BOM', depart: '13:45', arrive: '16:05', duration: '2h 20m', cabin: 'Economy Flex', price: 7290,  stops: 0, badge: 'Flexible',      aircraft: 'B737' },
  { id: 'SG-103',  airline: 'SpiceJet',           number: 'SG 103',  from: 'DEL', to: 'BOM', depart: '16:30', arrive: '18:50', duration: '2h 20m', cabin: 'Economy',      price: 5490,  stops: 0, badge: 'Budget pick',   aircraft: 'B737MAX' },
  { id: 'AI-803',  airline: 'Air India',          number: 'AI 803',  from: 'DEL', to: 'BOM', depart: '19:55', arrive: '22:05', duration: '2h 10m', cabin: 'Business',     price: 18500, stops: 0, badge: 'Business class',aircraft: 'A321' },

  // DEL ↔ BLR
  { id: '6E-2011', airline: 'IndiGo',             number: '6E 2011', from: 'DEL', to: 'BLR', depart: '07:00', arrive: '09:45', duration: '2h 45m', cabin: 'Economy',      price: 7200,  stops: 0, badge: 'Best value',    aircraft: 'A320neo' },
  { id: 'AI-501',  airline: 'Air India',          number: 'AI 501',  from: 'DEL', to: 'BLR', depart: '10:30', arrive: '13:20', duration: '2h 50m', cabin: 'Economy Flex', price: 8100,  stops: 0, badge: 'Recommended',   aircraft: 'A321' },
  { id: 'UK-820',  airline: 'Air India Express',  number: 'IX 820',  from: 'DEL', to: 'BLR', depart: '14:00', arrive: '16:55', duration: '2h 55m', cabin: 'Economy',      price: 6950,  stops: 0, badge: 'Good timing',   aircraft: 'B737' },

  // DEL ↔ HYD
  { id: '6E-6061', airline: 'IndiGo',             number: '6E 6061', from: 'DEL', to: 'HYD', depart: '08:15', arrive: '10:45', duration: '2h 30m', cabin: 'Economy',      price: 6400,  stops: 0, badge: 'Best value',    aircraft: 'A320neo' },
  { id: 'AI-403',  airline: 'Air India',          number: 'AI 403',  from: 'DEL', to: 'HYD', depart: '12:00', arrive: '14:35', duration: '2h 35m', cabin: 'Economy Flex', price: 7800,  stops: 0, badge: 'Recommended',   aircraft: 'A320' },

  // BOM ↔ BLR
  { id: '6E-891',  airline: 'IndiGo',             number: '6E 891',  from: 'BOM', to: 'BLR', depart: '06:30', arrive: '08:05', duration: '1h 35m', cabin: 'Economy',      price: 4200,  stops: 0, badge: 'Best value',    aircraft: 'A320neo' },
  { id: 'AI-621',  airline: 'Air India',          number: 'AI 621',  from: 'BOM', to: 'BLR', depart: '11:00', arrive: '12:40', duration: '1h 40m', cabin: 'Economy Flex', price: 5100,  stops: 0, badge: 'Recommended',   aircraft: 'A321' },

  // CCU (Kolkata) routes
  { id: '6E-777',  airline: 'IndiGo',             number: '6E 777',  from: 'DEL', to: 'CCU', depart: '09:40', arrive: '12:10', duration: '2h 30m', cabin: 'Economy',      price: 5600,  stops: 0, badge: 'Best value',    aircraft: 'A320neo' },
  { id: 'AI-721',  airline: 'Air India',          number: 'AI 721',  from: 'DEL', to: 'CCU', depart: '14:20', arrive: '16:55', duration: '2h 35m', cabin: 'Economy Flex', price: 6900,  stops: 0, badge: 'Recommended',   aircraft: 'A321' },
];

// ─────────────────────────────────────────────────────────────────────────────
// Hotel inventory  (city → hotels)
// ─────────────────────────────────────────────────────────────────────────────
const HOTELS = [
  // Mumbai
  { id: 'H-TAJ-BOM',    city: 'BOM', cityName: 'Mumbai',    name: 'Taj Mahal Palace',     area: 'Colaba',         stars: 5, nightlyRate: 18000, rating: 4.8, amenities: ['WiFi', 'Pool', 'Spa', 'Gym', 'Restaurant'], badge: 'Policy approved', image: '🏨' },
  { id: 'H-MAR-BOM',    city: 'BOM', cityName: 'Mumbai',    name: 'Marriott Juhu',        area: 'Juhu',           stars: 5, nightlyRate: 14500, rating: 4.6, amenities: ['WiFi', 'Pool', 'Gym', 'Restaurant'],        badge: 'Recommended',     image: '🏨' },
  { id: 'H-IBI-BOM',    city: 'BOM', cityName: 'Mumbai',    name: 'ibis Mumbai Airport',  area: 'Andheri East',   stars: 3, nightlyRate: 4200,  rating: 4.2, amenities: ['WiFi', 'Restaurant'],                      badge: 'Budget pick',     image: '🏩' },
  { id: 'H-NOV-BOM',    city: 'BOM', cityName: 'Mumbai',    name: 'Novotel Mumbai',       area: 'Juhu',           stars: 4, nightlyRate: 9500,  rating: 4.4, amenities: ['WiFi', 'Pool', 'Gym', 'Restaurant'],        badge: 'Best value',      image: '🏨' },

  // Bengaluru
  { id: 'H-LEE-BLR',    city: 'BLR', cityName: 'Bengaluru', name: 'The Leela Palace',     area: 'HAL Airport Rd', stars: 5, nightlyRate: 16000, rating: 4.9, amenities: ['WiFi', 'Pool', 'Spa', 'Gym', 'Restaurant'], badge: 'Policy approved', image: '🏨' },
  { id: 'H-ITC-BLR',    city: 'BLR', cityName: 'Bengaluru', name: 'ITC Gardenia',         area: 'Residency Rd',   stars: 5, nightlyRate: 12000, rating: 4.7, amenities: ['WiFi', 'Pool', 'Spa', 'Gym', 'Restaurant'], badge: 'Recommended',     image: '🏨' },
  { id: 'H-HIL-BLR',    city: 'BLR', cityName: 'Bengaluru', name: 'Hilton Bangalore',     area: 'Embassy GolfLinks',stars:5, nightlyRate: 11500, rating: 4.5, amenities: ['WiFi', 'Pool', 'Gym', 'Restaurant'],       badge: 'Best value',      image: '🏨' },
  { id: 'H-FOR-BLR',    city: 'BLR', cityName: 'Bengaluru', name: 'Ibis Bengaluru',       area: 'Hosur Road',     stars: 3, nightlyRate: 3800,  rating: 4.1, amenities: ['WiFi', 'Restaurant'],                      badge: 'Budget pick',     image: '🏩' },

  // Delhi
  { id: 'H-OBE-DEL',    city: 'DEL', cityName: 'Delhi',     name: 'The Oberoi New Delhi', area: 'Zakir Husain Marg',stars:5,nightlyRate: 22000, rating: 4.9, amenities: ['WiFi', 'Pool', 'Spa', 'Gym', 'Restaurant'], badge: 'Policy approved', image: '🏨' },
  { id: 'H-SHA-DEL',    city: 'DEL', cityName: 'Delhi',     name: 'Shangri-La Eros',      area: 'Connaught Place', stars: 5, nightlyRate: 15000, rating: 4.7, amenities: ['WiFi', 'Pool', 'Spa', 'Gym', 'Restaurant'], badge: 'Recommended',     image: '🏨' },
  { id: 'H-MAR-DEL',    city: 'DEL', cityName: 'Delhi',     name: 'Courtyard Marriott',   area: 'New Delhi',       stars: 4, nightlyRate: 8500,  rating: 4.3, amenities: ['WiFi', 'Gym', 'Restaurant'],               badge: 'Best value',      image: '🏨' },

  // Hyderabad
  { id: 'H-NOV-HYD',    city: 'HYD', cityName: 'Hyderabad', name: 'Novotel Hyderabad',    area: 'HICC',            stars: 5, nightlyRate: 9800,  rating: 4.5, amenities: ['WiFi', 'Pool', 'Gym', 'Restaurant'],        badge: 'Recommended',     image: '🏨' },
  { id: 'H-MAR-HYD',    city: 'HYD', cityName: 'Hyderabad', name: 'Marriott Hyderabad',   area: 'Banjara Hills',   stars: 5, nightlyRate: 11500, rating: 4.6, amenities: ['WiFi', 'Pool', 'Spa', 'Gym', 'Restaurant'], badge: 'Policy approved', image: '🏨' },
  { id: 'H-IBI-HYD',    city: 'HYD', cityName: 'Hyderabad', name: 'ibis Hyderabad',       area: 'Hitec City',      stars: 3, nightlyRate: 3500,  rating: 4.0, amenities: ['WiFi', 'Restaurant'],                      badge: 'Budget pick',     image: '🏩' },
];

// ─────────────────────────────────────────────────────────────────────────────
// Seat map generator — returns a realistic 30-row cabin grid
// ─────────────────────────────────────────────────────────────────────────────
function generateSeatMap(flightId) {
  const seed = flightId.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
  const pseudo = (n) => ((seed * 9301 + 49297 * (n + 1)) % 233280) / 233280;

  const rows = [];
  for (let row = 1; row <= 30; row++) {
    const isBusiness = row <= 4;
    const seats = isBusiness
      ? ['A', 'C', 'D', 'F']
      : ['A', 'B', 'C', 'D', 'E', 'F'];

    rows.push({
      row,
      type: isBusiness ? 'business' : row <= 10 ? 'extra_legroom' : 'economy',
      seats: seats.map(letter => ({
        seatId: `${row}${letter}`,
        letter,
        status: pseudo(row * 10 + letter.charCodeAt(0)) > 0.35 ? 'available' : 'occupied',
        window: letter === 'A' || letter === 'F',
        aisle: letter === 'C' || letter === 'D',
        extraLegroom: row <= 10 && !isBusiness,
        price: isBusiness ? 3500 : row <= 10 ? 600 : 0,
      })),
    });
  }
  return rows;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function empId(v) { return v || DEFAULT_EMPLOYEE_ID; }
function listFor(store, id) { return [...store.values()].filter(x => x.employeeId === id); }
function nightsBetween(checkin, checkout) {
  const d1 = new Date(checkin), d2 = new Date(checkout);
  return Math.max(1, Math.round((d2 - d1) / 86400000));
}

// ─────────────────────────────────────────────────────────────────────────────
// Routes — State
// ─────────────────────────────────────────────────────────────────────────────
router.get('/state', (req, res) => {
  const id = empId(req.query.employeeId);
  res.json({
    employeeId: id,
    bookings:      listFor(bookings, id),
    hotelBookings: listFor(hotelBookings, id),
    claims:        listFor(claims, id),
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/travel/card-transactions?employeeId=EMP001
// Proxy to Layer 3 so the travel dashboard can fetch card txns same-origin.
// ─────────────────────────────────────────────────────────────────────────────
router.get('/card-transactions', async (req, res) => {
  const id = empId(req.query.employeeId);
  try {
    const data = await layer3.getTransactions(id);
    res.json(data);
  } catch (err) {
    const status  = err.response?.status || 502;
    const message = err.response?.data?.detail || err.response?.data?.error || 'Failed to fetch transactions';
    res.status(status).json({ error: message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Routes — Flights
// ─────────────────────────────────────────────────────────────────────────────
router.post('/flights/search', (req, res) => {
  const { from = 'DEL', to = 'BOM', date, cabin } = req.body || {};
  const normalFrom = String(from).trim().toUpperCase();
  const normalTo   = String(to).trim().toUpperCase();

  if (!/^[A-Z]{3}$/.test(normalFrom) || !/^[A-Z]{3}$/.test(normalTo) || normalFrom === normalTo) {
    return res.status(422).json({ error: 'Choose two different 3-letter IATA airport codes (e.g. DEL, BOM, BLR).' });
  }

  let results = FLIGHTS.filter(f => f.from === normalFrom && f.to === normalTo);

  // If no direct match, return reverse-direction inventory with swapped codes
  if (!results.length) {
    results = FLIGHTS
      .filter(f => f.from === normalTo && f.to === normalFrom)
      .map(f => ({ ...f, from: normalFrom, to: normalTo, id: f.id + '-R' }));
  }

  // Filter by cabin if requested
  if (cabin && cabin !== 'ALL') {
    const cabinLower = cabin.toLowerCase();
    results = results.filter(f => f.cabin.toLowerCase().includes(cabinLower));
  }

  if (!results.length) {
    return res.status(200).json({
      searchedAt: new Date().toISOString(), date, from: normalFrom, to: normalTo, flights: [],
    });
  }

  res.json({
    searchedAt: new Date().toISOString(),
    date,
    from: normalFrom,
    to: normalTo,
    flights: results.map(f => ({ ...f, from: normalFrom, to: normalTo })),
  });
});

router.get('/flights/:id/seats', (req, res) => {
  // Normalise reversed IDs
  const flightId = req.params.id.replace(/-R$/, '');
  const flight   = FLIGHTS.find(f => f.id === flightId);
  if (!flight) return res.status(404).json({ error: 'Flight not found.' });

  res.json({
    flightId,
    airline:    flight.airline,
    number:     flight.number,
    from:       flight.from,
    to:         flight.to,
    depart:     flight.depart,
    aircraft:   flight.aircraft,
    seatMap:    generateSeatMap(flightId),
  });
});

router.post('/bookings', async (req, res) => {
  const { flight, travelDate, purpose, seat, employeeId: reqEmp } = req.body || {};
  if (!flight?.id || !travelDate || !purpose?.trim()) {
    return res.status(422).json({ error: 'Flight, travel date, and business purpose are required.' });
  }

  const rawId = flight.id.replace(/-R$/, '');
  const found = FLIGHTS.find(f => f.id === rawId);
  if (!found) return res.status(422).json({ error: 'The selected fare is no longer available.' });

  const id         = empId(reqEmp);
  const bookingId  = `TRIP-${uuidv4().slice(0, 8).toUpperCase()}`;
  const txnId      = `CCT-FLT-${uuidv4().slice(0, 8).toUpperCase()}`;
  const seatUpgrade = seat?.price || 0;
  const totalPrice  = found.price + seatUpgrade;
  const flightData  = {
    ...found,
    from:       flight.from || found.from,
    to:         flight.to   || found.to,
    selectedSeat: seat?.seatId || null,
    seatType:     seat?.seatId ? (found.cabin === 'Business' ? 'Business' : seat.extraLegroom ? 'Extra legroom' : 'Standard') : null,
  };

  try {
    await layer3.createCardTransaction({
      transactionId:   txnId,
      employeeId:      id,
      vendor:          `${flightData.airline} ${flightData.number}`,
      amount:          totalPrice,
      currency:        'INR',
      transactionDate: new Date().toISOString().slice(0, 10),
      cardLastFour:    '4242',
    });
  } catch (err) {
    const detail = err.response?.data?.detail || err.response?.data?.error || err.message;
    return res.status(502).json({ error: 'The booking could not be posted to the corporate card feed.', detail });
  }

  const booking = {
    bookingId, txnId, transactionId: txnId,
    employeeId: id, type: 'FLIGHT',
    flight: flightData, travelDate,
    purpose: purpose.trim(),
    totalPrice, seatUpgrade,
    status: 'CONFIRMED',
    bookedAt: new Date().toISOString(),
  };
  bookings.set(bookingId, booking);
  res.status(201).json(booking);
});

// ─────────────────────────────────────────────────────────────────────────────
// Routes — Hotels
// ─────────────────────────────────────────────────────────────────────────────
router.post('/hotels/search', (req, res) => {
  const { city, checkin, checkout } = req.body || {};
  const normalCity = String(city || '').trim().toUpperCase();

  if (!normalCity || normalCity.length < 2) {
    return res.status(422).json({ error: 'Please provide a destination city or IATA code.' });
  }
  if (!checkin || !checkout) {
    return res.status(422).json({ error: 'Check-in and check-out dates are required.' });
  }

  const nights = nightsBetween(checkin, checkout);
  if (nights < 1) return res.status(422).json({ error: 'Check-out must be after check-in.' });

  // Match by IATA code or city name (case-insensitive)
  const results = HOTELS.filter(h =>
    h.city === normalCity ||
    h.cityName.toUpperCase().startsWith(normalCity) ||
    h.cityName.toUpperCase() === normalCity
  );

  res.json({
    searchedAt: new Date().toISOString(),
    city: normalCity,
    checkin,
    checkout,
    nights,
    hotels: results.map(h => ({
      ...h,
      totalPrice: h.nightlyRate * nights,
      nights,
    })),
  });
});

router.post('/hotel-bookings', async (req, res) => {
  const { hotel, checkin, checkout, purpose, employeeId: reqEmp } = req.body || {};
  if (!hotel?.id || !checkin || !checkout || !purpose?.trim()) {
    return res.status(422).json({ error: 'Hotel, check-in, check-out, and business purpose are required.' });
  }

  const found = HOTELS.find(h => h.id === hotel.id);
  if (!found) return res.status(422).json({ error: 'Hotel is no longer available.' });

  const nights    = nightsBetween(checkin, checkout);
  const totalPrice = found.nightlyRate * nights;
  const id         = empId(reqEmp);
  const bookingId  = `HTL-${uuidv4().slice(0, 8).toUpperCase()}`;
  const txnId      = `CCT-HTL-${uuidv4().slice(0, 8).toUpperCase()}`;

  try {
    await layer3.createCardTransaction({
      transactionId:   txnId,
      employeeId:      id,
      vendor:          found.name,
      amount:          totalPrice,
      currency:        'INR',
      transactionDate: new Date().toISOString().slice(0, 10),
      cardLastFour:    '4242',
    });
  } catch (err) {
    const detail = err.response?.data?.detail || err.response?.data?.error || err.message;
    return res.status(502).json({ error: 'The hotel booking could not be posted to the corporate card feed.', detail });
  }

  const hbooking = {
    bookingId, txnId, transactionId: txnId,
    employeeId: id, type: 'HOTEL',
    hotel: { ...found, checkin, checkout, nights, totalPrice },
    checkin, checkout, nights, totalPrice,
    purpose: purpose.trim(),
    status: 'CONFIRMED',
    bookedAt: new Date().toISOString(),
  };
  hotelBookings.set(bookingId, hbooking);
  res.status(201).json(hbooking);
});

// ─────────────────────────────────────────────────────────────────────────────
// Routes — Claims
// ─────────────────────────────────────────────────────────────────────────────
router.post('/claims', async (req, res) => {
  const { bookingIds, title, employeeId: reqEmp } = req.body || {};
  const id = empId(reqEmp);

  const selectedFlights = (bookingIds || [])
    .map(bid => bookings.get(bid))
    .filter(b => b?.employeeId === id && !b.claimId);

  const selectedHotels = (bookingIds || [])
    .map(bid => hotelBookings.get(bid))
    .filter(b => b?.employeeId === id && !b.claimId);

  if (!selectedFlights.length && !selectedHotels.length) {
    return res.status(422).json({ error: 'Select at least one unclaimed confirmed booking.' });
  }

  const allBookings = [...selectedFlights, ...selectedHotels];
  const reportId = `RPT-TRAVEL-${uuidv4().slice(0, 8).toUpperCase()}`;
  const first    = allBookings[0];
  const reportName = (title || `Travel claim — ${first.type === 'HOTEL' ? first.hotel.name : `${first.flight.from} to ${first.flight.to}`}`).trim();

  const expenses = [
    ...selectedFlights.map(b => ({
      expenseType: 'FLIGHT',
      vendor: `${b.flight.airline} ${b.flight.number}`,
      amount: b.totalPrice,
      currency: 'INR',
      transactionDate: new Date().toISOString().slice(0, 10),
      city: b.flight.to,
      paymentType: 'CORPORATE_CARD',
      airfareDetail: { origin: b.flight.from, destination: b.flight.to, travelClass: 'ECONOMY', flightNumber: b.flight.number },
    })),
    ...selectedHotels.map(b => ({
      expenseType: 'HOTEL',
      vendor: b.hotel.name,
      amount: b.totalPrice,
      currency: 'INR',
      transactionDate: b.checkin,
      city: b.hotel.cityName,
      paymentType: 'CORPORATE_CARD',
      itemization: Array.from({ length: b.nights }, (_, i) => {
        const d = new Date(b.checkin);
        d.setDate(d.getDate() + i);
        return { nightDate: d.toISOString().slice(0, 10), roomRate: b.hotel.nightlyRate, taxes: Math.round(b.hotel.nightlyRate * 0.12) };
      }),
    })),
  ];

  try {
    await layer3.createReport(reportId, { employeeId: id, reportName, businessPurpose: first.purpose, policy: 'STANDARD', reportCategory: 'TRAVEL' });
    await layer3.submitExpenses(reportId, id, expenses);
    await layer3.submitReport(reportId);
  } catch (err) {
    const detail = err.response?.data?.detail || err.response?.data?.error || err.message;
    return res.status(502).json({ error: 'The claim could not be submitted to the expense system.', detail });
  }

  const total = allBookings.reduce((sum, b) => sum + (b.totalPrice || 0), 0);
  const claim = {
    claimId: reportId, employeeId: id, title: reportName,
    bookingIds: allBookings.map(b => b.bookingId),
    total, currency: 'INR', status: 'SUBMITTED',
    submittedAt: new Date().toISOString(),
  };
  claims.set(reportId, claim);
  allBookings.forEach(b => { b.claimId = reportId; });
  res.status(201).json(claim);
});

module.exports = router;
