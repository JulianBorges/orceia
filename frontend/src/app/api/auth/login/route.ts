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
