import { describe, expect, it } from 'vitest';
import { load } from './+page.js';

describe('home page data', () => {
	it('returns the product title', () => {
		expect(load()).toEqual({ title: 'FlakeGuard' });
	});
});
