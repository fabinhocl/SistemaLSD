
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

#larsaodomingos/urls.py
urlpatterns = [
    #path('admin/', admin.site.urls),
    path('', include('AppLSD.urls')),
    path('ged/', include('AppGED.urls', namespace='ged')),
    #path('', include('dashboard_lsd.urls')),     # Inclui todas as rotas do app, sem prefixo extra
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)