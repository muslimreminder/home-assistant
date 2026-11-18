// Writes tests/fixtures/adhan_reference.json with adhan-js itself, the
// library of the Muslim Reminder app, so that the tests can check the
// Python port time by time.
//
//   npm install --prefix /tmp/adhan-ref adhan@4.4.3
//   NODE_PATH=/tmp/adhan-ref/node_modules TZ=UTC node scripts/adhan_reference.mjs
//
// The parameters are built as the app builds them
// (computeMethodPrayerTimesObject in src/features/salat/services/SalatTime.service.ts):
// the method, the madhab, the minute adjustments and the TwilightAngle rule.
import { writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { CalculationMethod, CalculationParameters, Coordinates, HighLatitudeRule, Madhab, PrayerTimes, PolarCircleResolution } =
    require('adhan');

const other = (fajr, isha, interval = 0, maghrib = 0, adjustments = {}) => {
    const params = new CalculationParameters('Other', fajr, isha, interval, maghrib);
    params.methodAdjustments = { ...params.methodAdjustments, ...adjustments };
    return params;
};

const METHODS = {
    MUSLIM_WORLD_LEAGUE: () => CalculationMethod.MuslimWorldLeague(),
    MOONSIGHTING_COMMITEE: () => CalculationMethod.MoonsightingCommittee(),
    NORTH_AMERICA: () => CalculationMethod.NorthAmerica(),
    EGYPT: () => CalculationMethod.Egyptian(),
    UMM_ALQURA: () => CalculationMethod.UmmAlQura(),
    KARACHI: () => CalculationMethod.Karachi(),
    TEHRAN: () => CalculationMethod.Tehran(),
    KUWAIT: () => CalculationMethod.Kuwait(),
    SINGAPORE: () => CalculationMethod.Singapore(),
    QATAR: () => CalculationMethod.Qatar(),
    TURQEY: () => CalculationMethod.Turkey(),
    DUBAI: () => CalculationMethod.Dubai(),
    GULF: () => other(18.2, 18.2),
    MOROCCO: () => other(18.0, 17.0),
    GULF_2: () => other(19.5, undefined, 90),
    FRANCE_UOIF: () => other(12.0, 12.0),
    FRANCE_15: () => other(15.0, 15.0),
    FRANCE_18: () => other(18.0, 18.0),
    RUSSIA: () => other(16.0, 15.0),
    JAFARI: () => other(16.0, 14.0, 0, 4.0),
    KEMENAG: () => other(20.0, 18.0),
    ALGERIA: () => other(18.0, 17.0, 0, 0, { maghrib: 3 }),
    BRUNEI: () => other(20.0, 18.0),
    TUNISIA: () => other(18.0, 18.0),
};

const PLACES = {
    paris: [48.8566, 2.3522],
    london: [51.5072, -0.1276],
    oslo: [59.9139, 10.7522],
    reykjavik: [64.1466, -21.9426],
    tromso: [69.6492, 18.9553],
    makkah: [21.4225, 39.8262],
    casablanca: [33.5731, -7.5898],
    algiers: [36.7538, 3.0588],
    istanbul: [41.0082, 28.9784],
    tehran: [35.6892, 51.389],
    karachi: [24.8607, 67.0011],
    jakarta: [-6.2088, 106.8456],
    singapore: [1.3521, 103.8198],
    sydney: [-33.8688, 151.2093],
    new_york: [40.7128, -74.006],
    montreal: [45.5017, -73.5673],
};

const DATES = ['2026-01-01', '2026-03-29', '2026-06-21', '2026-09-23', '2026-10-25', '2026-12-21', '2027-02-28', '2028-02-29'];

// adhan-js rounds the seconds but keeps the milliseconds of a time derived
// from a night fraction (e.g. 03:58:00.142): they are dropped, the port
// returns whole seconds.
const iso = (date) => (Number.isNaN(date.getTime()) ? null : date.toISOString().replace(/\.\d{3}Z$/, 'Z'));

const cases = [];
for (const [place, [latitude, longitude]] of Object.entries(PLACES)) {
    for (const day of DATES) {
        const [y, m, d] = day.split('-').map(Number);
        for (const [method, build] of Object.entries(METHODS)) {
            for (const madhab of ['shafi', 'hanafi']) {
                const params = build();
                params.madhab = madhab === 'hanafi' ? Madhab.Hanafi : Madhab.Shafi;
                params.highLatitudeRule = HighLatitudeRule.TwilightAngle;
                const adjusted = method === 'FRANCE_18' && madhab === 'hanafi';
                if (adjusted) params.adjustments = { fajr: -2, sunrise: 1, dhuhr: 3, asr: -4, maghrib: 5, isha: -6 };
                const times = new PrayerTimes(new Coordinates(latitude, longitude), new Date(y, m - 1, d), params);
                cases.push({
                    place, latitude, longitude, day, method, madhab, adjusted,
                    times: Object.fromEntries(['fajr', 'sunrise', 'dhuhr', 'asr', 'maghrib', 'isha'].map((p) => [p, iso(times[p])])),
                });
            }
        }
        // Defaults of adhan-js (middle of the night) and the polar resolutions.
        for (const rule of ['middleofthenight', 'seventhofthenight']) {
            for (const polar of ['Unresolved', 'AqrabBalad', 'AqrabYaum']) {
                const params = CalculationMethod.MuslimWorldLeague();
                params.highLatitudeRule = rule;
                params.polarCircleResolution = PolarCircleResolution[polar];
                const times = new PrayerTimes(new Coordinates(latitude, longitude), new Date(y, m - 1, d), params);
                cases.push({
                    place, latitude, longitude, day, method: 'MUSLIM_WORLD_LEAGUE', madhab: 'shafi', adjusted: false, rule, polar,
                    times: Object.fromEntries(['fajr', 'sunrise', 'dhuhr', 'asr', 'maghrib', 'isha'].map((p) => [p, iso(times[p])])),
                });
            }
        }
    }
}

writeFileSync(new URL('../tests/fixtures/adhan_reference.json', import.meta.url), JSON.stringify(cases) + '\n');
console.log(`${cases.length} cases`);
