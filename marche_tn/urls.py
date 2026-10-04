from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.templatetags.static import static as fichier_static
from django.views.generic import RedirectView
from comptes import views as comptes_views

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url=fichier_static('img/favicon.ico'), permanent=False)),
    path('admin/', admin.site.urls),
    path('gestion/', include('dashboard.urls')),
    path('compte/', include('comptes.urls')),
    path('registre/', comptes_views.registre, name='registre'),
    path('accounts/', include('allauth.urls')),
    path('', include('boutique.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')
