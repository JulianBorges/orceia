import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
    try {
        const body = await request.json();
        const { tenant_id } = body;

        if (!tenant_id || tenant_id.trim() === '') {
            return NextResponse.json({ error: 'tenant_id é obrigatório' }, { status: 400 });
        }

        const normalizedTenant = tenant_id.trim().toLowerCase().replace(/[^a-z0-9]/g, '_');

        // Valida o tenant contra o banco antes de emitir o cookie de sessão.
        // Impede que qualquer string arbitrária seja aceita como tenant válido.
        const backendUrl = process.env.BACKEND_API_URL || 'http://127.0.0.1:8000';
        const apiSecret = process.env.API_SECRET_KEY;
        if (!apiSecret) {
            return NextResponse.json({ error: 'Configuração de servidor inválida' }, { status: 500 });
        }

        const validation = await fetch(`${backendUrl}/auth/validate-tenant`, {
            method: 'GET',
            headers: {
                'x-api-secret': apiSecret,
                'x-tenant-id': normalizedTenant,
            },
        });

        if (!validation.ok) {
            const detail = await validation.json().catch(() => ({}));
            return NextResponse.json(
                { error: detail?.detail || 'Tenant não autorizado.' },
                { status: 401 }
            );
        }

        cookies().set({
            name: 'orceia_tenant_session',
            value: normalizedTenant,
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            path: '/',
            maxAge: 60 * 60 * 24 * 7
        });

        return NextResponse.json({ status: 'success', tenant: normalizedTenant });
    } catch (error) {
        return NextResponse.json({ error: 'Bad Request' }, { status: 400 });
    }
}

