//
//  CryptoIdentityConcurrencyTests.swift
//  PosteRestante
//
//  Created by Muhammad Akbar Reishandy on 11/09/26.
//

import XCTest
import CryptoKit
@testable import PosteRestante

final class CryptoIdentityConcurrencyTests: XCTestCase {
	private let testService = "id.reishandy.PosteRestante.tests.concurrency"
	private var sut: CryptoIdentityManager!
	
	override func setUp() async throws {
		try await super.setUp()
		sut = CryptoIdentityManager(service: testService, account: "concurrent-\(UUID().uuidString)")
	}
	
	override func tearDown() async throws {
		try? await sut.deleteIdentityKey()
		sut = nil
		try await super.tearDown()
	}
	
	func test_concurrentKeyGeneration_resolvesDeterministicallyWithoutCrashing() async throws {
		// Fire 20 parallel tasks attempting to getOrCreate the private key simultaneously
		let results = try await withThrowingTaskGroup(of: Data.self, returning: [Data].self) { group in
			for _ in 0..<20 {
				group.addTask {
					let key = try await self.sut.getOrCreatePrivateKey()
					return key.rawRepresentation
				}
			}
			
			var keys: [Data] = []
			for try await keyData in group {
				keys.append(keyData)
			}
			return keys
		}
		
		XCTAssertEqual(results.count, 20)
		// Every single concurrent task must have resolved to the exact same key bytes
		let firstKey = results[0]
		XCTAssertTrue(results.allSatisfy { $0 == firstKey })
	}
}
