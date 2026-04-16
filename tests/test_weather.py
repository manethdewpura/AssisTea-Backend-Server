"""Unit tests for weather interpolation, history building, and ML weather heuristics."""

from types import SimpleNamespace

import pytest

from app.models.weather_records import (
    build_historical_data_for_prediction,
    interpolate_weather_data,
)
from app.models import weather_records
from app.ml.predictor import WeatherMLPredictor


class _FakeQuery:
    """Minimal query stub for chaining filter/order/limit in tests."""

    def __init__(self, records):
        self._records = list(records)
        self._limit = None

    def filter_by(self, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def all(self):
        if self._limit is None:
            return list(self._records)
        return list(self._records)[: self._limit]


class _DummyColumn:
    """Column-like comparator used to bypass SQLAlchemy expressions in unit tests."""

    def __ge__(self, _other):
        return True

    def __le__(self, _other):
        return True

    def __eq__(self, _other):
        return True

    def asc(self):
        return self

    def desc(self):
        return self


class _FakeWeatherCurrentModel:
    measured_at = _DummyColumn()
    is_ml_generated = _DummyColumn()
    timestamp = _DummyColumn()
    location_id = _DummyColumn()
    query = _FakeQuery([])


class _FakeWeatherForecastModel:
    forecast_dt = _DummyColumn()
    query = _FakeQuery([])


def _weather_current_row(ts_ms, temp=25.0, source_name="City A"):
    return SimpleNamespace(
        measured_at=ts_ms,
        timestamp=ts_ms,
        temp=temp,
        feels_like=temp,
        temp_min=temp - 1,
        temp_max=temp + 1,
        pressure=1010.0,
        humidity=80.0,
        wind_speed=2.0,
        wind_deg=180.0,
        rain_1h=0.0,
        rain_3h=0.0,
        clouds_all=20,
        location_id=1,
        location_name=source_name,
        country="ID",
        coord_lat=-6.2,
        coord_lon=106.8,
        is_ml_generated=False,
    )


def _weather_forecast_row(forecast_dt_sec, temp=22.0, city_name="City A"):
    return SimpleNamespace(
        forecast_dt=forecast_dt_sec,
        temp=temp,
        feels_like=temp,
        temp_min=temp - 1,
        temp_max=temp + 1,
        pressure=1008.0,
        humidity=82.0,
        wind_speed=2.5,
        wind_deg=170.0,
        rain_1h=0.0,
        rain_3h=0.0,
        clouds_all=45,
        city_id=1,
        city_name=city_name,
        city_country="ID",
        city_coord_lat=-6.2,
        city_coord_lon=106.8,
    )


class TestInterpolateWeatherData:
    def test_continuous_data_noop(self):
        base = 1_700_000_000_000
        data = [
            {"timestamp": base, "temp": 24.0, "feels_like": 24.0, "temp_min": 23.0, "temp_max": 25.0, "pressure": 1010.0, "humidity": 80.0, "wind_speed": 2.0, "wind_deg": 90.0, "clouds_all": 20, "rain_1h": 0.0, "rain_3h": 0.0},
            {"timestamp": base + 3_600_000, "temp": 25.0, "feels_like": 25.0, "temp_min": 24.0, "temp_max": 26.0, "pressure": 1011.0, "humidity": 79.0, "wind_speed": 2.1, "wind_deg": 90.0, "clouds_all": 25, "rain_1h": 0.0, "rain_3h": 0.0},
            {"timestamp": base + 7_200_000, "temp": 26.0, "feels_like": 26.0, "temp_min": 25.0, "temp_max": 27.0, "pressure": 1012.0, "humidity": 78.0, "wind_speed": 2.2, "wind_deg": 90.0, "clouds_all": 30, "rain_1h": 0.0, "rain_3h": 0.0},
        ]

        out, count = interpolate_weather_data(data, lookback_hours=3)
        assert count == 0
        assert [r["timestamp"] for r in out] == [r["timestamp"] for r in data]

    def test_gaps_are_interpolated(self):
        base = 1_700_000_000_000
        data = [
            {"timestamp": base, "temp": 24.0, "feels_like": 24.0, "temp_min": 23.0, "temp_max": 25.0, "pressure": 1010.0, "humidity": 80.0, "wind_speed": 2.0, "wind_deg": 90.0, "clouds_all": 20, "rain_1h": 1.0, "rain_3h": 1.5},
            {"timestamp": base + 7_200_000, "temp": 26.0, "feels_like": 26.0, "temp_min": 25.0, "temp_max": 27.0, "pressure": 1012.0, "humidity": 78.0, "wind_speed": 3.0, "wind_deg": 110.0, "clouds_all": 40, "rain_1h": 3.0, "rain_3h": 3.5},
        ]

        out, count = interpolate_weather_data(data, lookback_hours=3)
        assert len(out) == 3
        assert count == 2
        # Function keeps the latest lookback window, so expected timeline is +1h, +2h, +3h.
        assert [r["timestamp"] for r in out] == [
            base + 3_600_000,
            base + 7_200_000,
            base + 10_800_000,
        ]
        # Rain should be interpolated between non-zero neighbors, not zero-filled.
        assert 1.0 < out[0]["rain_1h"] < 3.0

    def test_single_record_forward_fill_with_rain_decay(self):
        base = 1_700_000_000_000
        data = [
            {"timestamp": base, "temp": 24.0, "feels_like": 24.0, "temp_min": 23.0, "temp_max": 25.0, "pressure": 1010.0, "humidity": 80.0, "wind_speed": 2.0, "wind_deg": 90.0, "clouds_all": 20, "rain_1h": 4.0, "rain_3h": 2.0},
        ]

        out, count = interpolate_weather_data(data, lookback_hours=3)
        assert len(out) == 3
        assert count == 3
        assert out[1]["rain_1h"] > 0.0
        assert out[1]["rain_1h"] < out[0]["rain_1h"]

    def test_empty_data_returns_empty(self):
        out, count = interpolate_weather_data([], lookback_hours=5)
        assert out == []
        assert count == 0


class TestBuildHistoricalDataForPrediction:
    def test_sufficient_data_no_forecast_needed(self, monkeypatch):
        base = 1_700_000_000_000
        current_rows = [_weather_current_row(base + i * 3_600_000, temp=20 + i) for i in range(4)]

        _FakeWeatherCurrentModel.query = _FakeQuery(current_rows)
        _FakeWeatherForecastModel.query = _FakeQuery([])
        monkeypatch.setattr(weather_records, "WeatherCurrent", _FakeWeatherCurrentModel)
        monkeypatch.setattr(weather_records, "WeatherForecast", _FakeWeatherForecastModel)

        historical, city_info, source = build_historical_data_for_prediction(lookback_hours=4, city_id=1)
        assert len(historical) == 4
        assert source["forecast_count"] == 0
        assert source["has_sufficient_data"] is True
        assert city_info["id"] == 1

    def test_insufficient_data_uses_interpolation(self, monkeypatch):
        base = 1_700_000_000_000
        current_rows = [_weather_current_row(base, temp=25.0)]

        _FakeWeatherCurrentModel.query = _FakeQuery(current_rows)
        _FakeWeatherForecastModel.query = _FakeQuery([])
        monkeypatch.setattr(weather_records, "WeatherCurrent", _FakeWeatherCurrentModel)
        monkeypatch.setattr(weather_records, "WeatherForecast", _FakeWeatherForecastModel)

        historical, _city_info, source = build_historical_data_for_prediction(lookback_hours=4, city_id=1)
        assert len(historical) == 4
        assert source["interpolated_count"] > 0
        assert source["has_sufficient_data"] is True

    def test_dedup_prefers_current_over_forecast(self, monkeypatch):
        # Use same timestamp for current and past-forecast rows. Current should win.
        shared_ts_ms = 1_700_000_000_000
        current_rows = [_weather_current_row(shared_ts_ms, temp=31.0)]
        forecast_rows = [_weather_forecast_row(shared_ts_ms // 1000, temp=19.0)]

        _FakeWeatherCurrentModel.query = _FakeQuery(current_rows)
        _FakeWeatherForecastModel.query = _FakeQuery(forecast_rows)
        monkeypatch.setattr(weather_records, "WeatherCurrent", _FakeWeatherCurrentModel)
        monkeypatch.setattr(weather_records, "WeatherForecast", _FakeWeatherForecastModel)

        historical, _city_info, _source = build_historical_data_for_prediction(lookback_hours=1, city_id=1)
        row_at_shared_ts = next(r for r in historical if r["timestamp"] == shared_ts_ms)
        assert row_at_shared_ts["temp"] == 31.0


class TestWeatherPredictorHeuristics:
    @pytest.fixture
    def predictor(self):
        # Bypass __init__ (which loads TensorFlow model) for pure logic tests.
        return WeatherMLPredictor.__new__(WeatherMLPredictor)

    def test_weather_condition_classification(self, predictor):
        drizzle = predictor._classify_weather_condition(
            rain_1h=0.2, clouds=20, humidity=70.0, wind_speed=1.0, pred_hour=14
        )
        mist = predictor._classify_weather_condition(
            rain_1h=0.0, clouds=40, humidity=98.0, wind_speed=1.5, pred_hour=2
        )
        clear_night = predictor._classify_weather_condition(
            rain_1h=0.0, clouds=5, humidity=60.0, wind_speed=1.0, pred_hour=23
        )

        assert drizzle == ("Drizzle", "light drizzle", "09d")
        assert mist == ("Mist", "mist", "50n")
        assert clear_night == ("Clear", "clear sky", "01n")

    def test_visibility_derivation(self, predictor):
        assert predictor._estimate_visibility(rain_1h=8.0, humidity=80.0) == 2000
        assert predictor._estimate_visibility(rain_1h=3.0, humidity=80.0) == 5000
        assert predictor._estimate_visibility(rain_1h=0.2, humidity=80.0) == 7000
        assert predictor._estimate_visibility(rain_1h=0.0, humidity=97.0) == 4000
        assert predictor._estimate_visibility(rain_1h=0.0, humidity=70.0) == 10000
