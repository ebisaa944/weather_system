from django.apps import AppConfig


class WeatherConfig(AppConfig):
    name = 'weather'

    def ready(self):
        """
        Patch Django's template context copy behavior for Python 3.14.
        Django 4.2's use of copy(super()) breaks in this environment.
        """
        from django.template.context import BaseContext

        if getattr(BaseContext, '_weather_copy_patch', False):
            return

        def _safe_copy(self):
            duplicate = object.__new__(self.__class__)
            duplicate.__dict__ = self.__dict__.copy()
            duplicate.dicts = self.dicts[:]
            return duplicate

        BaseContext.__copy__ = _safe_copy
        BaseContext._weather_copy_patch = True
