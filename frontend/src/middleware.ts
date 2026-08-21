import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
    const isLoginPage = request.nextUrl.pathname === '/login';
    const isApiAuth = request.nextUrl.pathname.startsWith('/api/auth');
    
    // Deixa rotas públicas passarem
    if (isLoginPage || isApiAuth) {
        return NextResponse.next();
    }

    // Checa o cookie de sessão do Tenant
    const tenantSession = request.cookies.get('orceia_tenant_session');

    // Se não tiver logado, manda pro login
    if (!tenantSession?.value) {
        return NextResponse.redirect(new URL('/login', request.url));
    }

    // Se tiver logado, clona a requisição e injeta o header de segurança X-Tenant-ID
    // Esse header será usado por /api/proxy para passar adiante pro Backend
    const requestHeaders = new Headers(request.headers);
    requestHeaders.set('x-tenant-id', tenantSession.value);

    return NextResponse.next({
        request: {
            headers: requestHeaders,
        },
    });
}

export const config = {
    matcher: [
        /*
         * Match all request paths except for the ones starting with:
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico (favicon file)
         */
        '/((?!_next/static|_next/image|favicon.ico).*)',
    ],
};
